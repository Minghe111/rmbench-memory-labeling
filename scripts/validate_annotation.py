#!/usr/bin/env python3
"""Check the structure, causal references, and declared facts of a local RMBench review."""
from argparse import ArgumentParser
from bisect import bisect_right
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


SCHEMA = 'rmbench.memory-review.v1'
CAMERAS = {'head', 'left_wrist', 'right_wrist'}
CLOCKS = ('observable_onset', 'outcome_frame', 'handoff_frame')
FACT_KINDS = {'binding', 'outcome', 'state'}


class ReviewError(ValueError):
    """A review record violates its declared structure or time bounds."""


def require(condition, where, message):
    if not condition:
        raise ReviewError(f'{where}: {message}')


def mapping(value, where):
    require(isinstance(value, dict), where, 'expected an object')
    return value


def rows(value, where):
    require(isinstance(value, list), where, 'expected an array')
    return value


def field(record, key, where):
    require(key in record, where, f'missing {key}')
    return record[key]


def text(value, where):
    require(isinstance(value, str) and bool(value.strip()), where, 'expected nonempty text')
    return value


def integer(value, lower, upper, where):
    require(type(value) is int and lower <= value <= upper, where,
            f'expected an integer in [{lower}, {upper}]')
    return value


def evidence(value, frame, where):
    items = rows(value, where)
    require(items, where, 'a known observation requires at least one evidence image')
    seen = set()
    for i, raw in enumerate(items):
        loc = f'{where}[{i}]'
        item = mapping(raw, loc)
        observed = integer(item.get('frame'), 0, frame, loc + '.frame')
        camera = text(item.get('camera'), loc + '.camera')
        require(camera in CAMERAS, loc, 'expected head, left_wrist, or right_wrist')
        require((observed, camera) not in seen, loc, 'duplicate image')
        if 'sha256' in item:
            checksum = text(item['sha256'], loc + '.sha256')
            require(re.fullmatch(r'[0-9a-fA-F]{64}', checksum) is not None,
                    loc + '.sha256', 'expected 64 hexadecimal characters')
        seen.add((observed, camera))


def source_segments(value, count, where):
    segments, cursor = [], 0
    for i, raw in enumerate(rows(value, where)):
        loc = f'{where}[{i}]'
        row = mapping(raw, loc)
        start = integer(row.get('start'), 0, count - 1, loc + '.start')
        end = integer(row.get('end'), start + 1, count, loc + '.end')
        require(start == cursor, loc, 'official spans must be contiguous')
        segments.append((start, end, text(row.get('text'), loc + '.text')))
        cursor = end
    require(cursor == count, where, 'official spans must cover the declared trajectory')
    return segments


def original_segments(value, key, where):
    entries = rows(value.get(key), where)
    segments, cursor = [], 0
    for i, row in enumerate(entries):
        loc = f'{where}[{i}]'
        require(isinstance(row, list) and len(row) == 2, loc, 'expected [text, duration]')
        content = text(row[0], loc + '.text')
        duration = row[1]
        require(type(duration) is int and duration > 0, loc, 'duration must be a positive integer')
        segments.append((cursor, cursor + duration, content))
        cursor += duration
    return segments


def validate_stages(value, segments, count, where, totals):
    entries = rows(value, where)
    require(not entries or segments, where, 'stage indices need source_subtasks')
    used = set()
    for i, raw in enumerate(entries):
        loc = f'{where}[{i}]'
        row = mapping(raw, loc)
        index = integer(row.get('subtask_index'), 0, len(segments) - 1, loc + '.subtask_index')
        require(index not in used, loc, 'duplicate review of the same source stage')
        used.add(index)
        support = mapping(row.get('evidence'), loc + '.evidence')
        require(support.keys() <= set(CLOCKS), loc + '.evidence', 'unknown clock name')
        for clock in CLOCKS:
            present = field(row, clock, loc)
            if present is None:
                require(clock not in support or support[clock] == [], loc + '.' + clock,
                        'a null clock has no claimed evidence timestamp')
                totals['null_clocks'] += 1
                continue
            frame = integer(present, 0, count - 1, loc + '.' + clock)
            evidence(support.get(clock), frame, loc + '.evidence.' + clock)
        totals['stages'] += 1


def snapshot_frames(value, count, scope, where):
    frames = []
    for i, raw in enumerate(rows(value, where)):
        loc = f'{where}[{i}]'
        row = mapping(raw, loc)
        lower = frames[-1] + 1 if frames else 0
        frame = integer(row.get('frame'), lower, count - 1, loc + '.frame')
        text(row.get('memory'), loc + '.memory')
        evidence(row.get('evidence'), frame, loc + '.evidence')
        frames.append(frame)
    require(frames, where, 'expected at least one Memory snapshot')
    if scope == 'complete':
        require(frames[0] == 0 and frames[-1] == count - 1, where,
                'complete trajectories need initial and true terminal snapshots')
    return frames


def at_or_before(frames, frame):
    if frame is None:
        return None
    index = bisect_right(frames, frame)
    return frames[index - 1] if index else None


def validate_decisions(value, snapshots, count, scope, where):
    entries = rows(value, where)
    require(entries, where, 'expected at least one declared decision')
    previous = None
    for index, raw in enumerate(entries):
        loc = f'{where}[{index}]'
        row = mapping(raw, loc)
        lower = 0 if previous is None else previous + 1
        frame = integer(row.get('frame'), lower, count - 1, loc + '.frame')
        target = at_or_before(snapshots, frame)
        history = at_or_before(snapshots, previous)
        for key, expected in (
            ('prev_decision_frame', previous), ('memory_frame', target), ('previous_memory_frame', history),
        ):
            value = field(row, key, loc)
            require(value is None or type(value) is int, loc + '.' + key,
                    'expected a frame number or null')
            require(value == expected, loc + '.' + key, f'expected {expected!r}, got {value!r}')
        memory_role, subtask_role = row.get('supervise_memory'), row.get('supervise_subtask')
        require(type(memory_role) is bool and type(subtask_role) is bool, loc,
                'supervise_memory and supervise_subtask must be booleans')
        require(not memory_role or target is not None, loc,
                'Memory supervision needs a causal snapshot')
        if frame == count - 1:
            require(not subtask_role, loc, 'terminal decisions cannot supervise Subtask')
        previous = frame
    if scope == 'complete':
        require(previous == count - 1, where, 'complete decision trace needs the true terminal frame')
    return len(entries)


def fact_intervals(value, count, where):
    facts = {}
    by_property = defaultdict(list)
    entries = rows(value, where)
    require(entries, where, 'fact review requires at least one fact')
    for i, raw in enumerate(entries):
        loc = f'{where}[{i}]'
        row = mapping(raw, loc)
        fact_id = text(row.get('id'), loc + '.id')
        require(fact_id not in facts, loc, f'duplicate fact ID {fact_id!r}')
        kind = text(row.get('kind'), loc + '.kind')
        require(kind in FACT_KINDS, loc, 'expected binding, outcome, or state')
        subject = text(row.get('subject'), loc + '.subject')
        predicate = text(row.get('predicate'), loc + '.predicate')
        text(row.get('value'), loc + '.value')
        required_in_memory = row.get('required_in_memory', False)
        require(type(required_in_memory) is bool, loc + '.required_in_memory', 'expected a boolean')
        start = integer(row.get('start'), 0, count - 1, loc + '.start')
        declared_end = field(row, 'end', loc)
        end = count if declared_end is None else integer(declared_end, start + 1, count, loc + '.end')
        evidence(row.get('evidence'), start, loc + '.evidence')
        end_support = row.get('end_evidence', [])
        if end < count or end_support != []:
            require(declared_end is not None, loc, 'a fact with no end cannot declare end evidence')
            evidence(end_support, min(end, count - 1), loc + '.end_evidence')
            require(max(item['frame'] for item in end_support) >= start, loc,
                    'end evidence must reach the fact start or later')
        facts[fact_id] = (start, end, required_in_memory)
        by_property[kind, subject, predicate].append((start, end, fact_id))
    for prop, intervals in by_property.items():
        ordered = sorted(intervals)
        for left, right in zip(ordered, ordered[1:]):
            require(left[1] <= right[0], where,
                    f'overlapping facts {left[2]!r} and {right[2]!r} for {prop!r}')
    return facts


def snapshot_claims(snapshot, frame, end, facts, where):
    entries = rows(snapshot.get('claims'), where + '.claims')
    require(entries, where, 'fact review requires at least one claim per Memory snapshot')
    parts = []
    referenced = set()
    for i, raw in enumerate(entries):
        loc = f'{where}.claims[{i}]'
        claim = mapping(raw, loc)
        parts.append(text(claim.get('text'), loc + '.text'))
        ids = rows(claim.get('facts'), loc + '.facts')
        require(ids, loc, 'claim must reference at least one fact')
        seen = set()
        for raw_id in ids:
            fact_id = text(raw_id, loc + '.facts')
            require(fact_id not in seen, loc, f'duplicate reference to fact {fact_id!r}')
            require(fact_id in facts, loc, f'unknown fact {fact_id!r}')
            start, stop, _ = facts[fact_id]
            require(start <= frame, loc, f'fact {fact_id!r} starts at {start}, after snapshot {frame}')
            require(end <= stop, loc,
                    f'fact {fact_id!r} expires at {stop}, before snapshot interval [{frame}, {end}) ends')
            seen.add(fact_id)
        referenced.update(seen)
    require(' '.join(' '.join(parts).split()) == ' '.join(snapshot['memory'].split()), where,
            'claim texts must cover the Memory text in order')
    return referenced, len(entries)


def validate_fact_review(ep, frames, count, where, totals):
    snapshots = ep['snapshots']
    if 'facts' not in ep:
        require('review_end' not in ep and all('claims' not in row for row in snapshots), where,
                'claims and review_end require facts')
        return
    review_end = count
    if 'review_end' in ep:
        require(ep['scope'] == 'partial', where, 'review_end is only for partial fact review')
        review_end = integer(ep['review_end'], 1, count, where + '.review_end')
        require(frames[-1] < review_end, where, 'snapshots must be before review_end')
        if 'decisions' in ep:
            require(ep['decisions'][-1]['frame'] < review_end, where, 'decisions must be before review_end')
    facts = fact_intervals(ep['facts'], count, where + '.facts')
    required = [(fact_id, start, stop) for fact_id, (start, stop, needed) in facts.items() if needed]
    referenced = {}
    for i, (snapshot, frame, end) in enumerate(zip(snapshots, frames, frames[1:] + [review_end])):
        loc = f'{where}.snapshots[{i}]'
        references, number = snapshot_claims(snapshot, frame, end, facts, loc)
        for fact_id, start, stop in required:
            if start < end and frame < stop:
                require(fact_id in references, loc,
                        f'required fact {fact_id!r} missing from snapshot interval [{frame}, {end})')
        referenced[frame] = references
        totals['claims'] += number
    totals['fact_episodes'] += 1
    totals['facts'] += len(facts)
    if 'decisions' in ep:
        sampled = set()
        for decision in ep['decisions']:
            if decision['supervise_memory']:
                sampled.update(referenced[decision['memory_frame']])
        totals['facts_with_decision_trace'] += len(facts)
        totals['facts_in_supervised_targets'] += len(sampled)
        totals['facts_not_in_supervised_targets'] += len(facts) - len(sampled)


def validate(document, official_annotations):
    top = mapping(document, 'document')
    require(top.get('schema') == SCHEMA, 'schema', f'expected {SCHEMA!r}')
    episodes = rows(top.get('episodes'), 'episodes')
    require(episodes, 'episodes', 'expected at least one reviewed trajectory')
    visited, compared, totals = set(), set(), Counter()
    for i, raw in enumerate(episodes):
        loc = f'episodes[{i}]'
        ep = mapping(raw, loc)
        identity = tuple(text(ep.get(key), loc + '.' + key)
                         for key in ('task_id', 'collection', 'episode_id'))
        require(identity not in visited, loc, 'duplicate trajectory')
        visited.add(identity)
        count = ep.get('frame_count')
        require(type(count) is int and count > 0, loc + '.frame_count', 'expected a positive frame count')
        scope = ep.get('scope')
        require(scope in ('partial', 'complete'), loc + '.scope', 'expected partial or complete')
        segments = source_segments(ep['source_subtasks'], count, loc + '.source_subtasks') \
            if 'source_subtasks' in ep else []
        group = identity[:2]
        if group in official_annotations:
            official = original_segments(official_annotations[group], identity[2], loc + '.official')
            require(segments == official, loc + '.source_subtasks',
                    'recorded spans or text differ from the supplied official annotations')
            compared.add(group)
            totals['compared_episodes'] += 1
        validate_stages(ep.get('stages', []), segments, count, loc + '.stages', totals)
        frames = snapshot_frames(ep.get('snapshots'), count, scope, loc + '.snapshots')
        if 'decisions' in ep:
            totals['decisions'] += validate_decisions(ep['decisions'], frames, count, scope, loc + '.decisions')
        validate_fact_review(ep, frames, count, loc, totals)
        totals['snapshots'] += len(frames)
        totals[scope + '_episodes'] += 1
    require(compared == official_annotations.keys(), 'official annotations',
            'each supplied task and collection must appear in the review')
    return totals


def read_json(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('review', type=Path)
    parser.add_argument('--official-annotations', nargs=3, action='append', default=[],
                        metavar=('TASK', 'COLLECTION', 'FILE'),
                        help='compare supplied source_subtasks with the original language_annotation.json')
    args = parser.parse_args()
    try:
        official = {}
        for task, collection, path in args.official_annotations:
            key = (task, collection)
            require(key not in official, 'official annotations', f'duplicate task and collection: {key!r}')
            official[key] = mapping(read_json(path), str(path))
        counts = validate(read_json(args.review), official)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Annotation check failed: {exc}\n')
    print(f"Checked {counts['partial_episodes'] + counts['complete_episodes']} trajectory record(s) "
          f"({counts['partial_episodes']} partial), {counts['snapshots']} Memory snapshot(s), "
          f"{counts['stages']} stage(s), {counts['decisions']} decision(s), "
          f"and {counts['compared_episodes']} supplied official annotation comparison(s).")
    print(f"Structurally valid. Null stage clocks: {counts['null_clocks']}. "
          'Visual claims still need image review.')
    if counts['fact_episodes']:
        print(f"Validated {counts['facts']} fact(s) and {counts['claims']} claim(s) "
              f"across {counts['fact_episodes']} fact review(s).")
    if counts['facts_with_decision_trace']:
        print(f"Supervised Memory targets include {counts['facts_in_supervised_targets']} of "
              f"{counts['facts_with_decision_trace']} fact(s) with a decision trace "
              f"({counts['facts_not_in_supervised_targets']} absent).")


if __name__ == '__main__':
    main()
