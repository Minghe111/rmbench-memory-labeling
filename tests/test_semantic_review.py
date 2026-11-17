from copy import deepcopy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from validate_annotation import ReviewError, read_json, validate


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.review = read_json(ROOT / 'examples' / 'semantic-review.json')
        self.button, self.cover, self.battery = self.review['episodes']

    def test_three_synthetic_trajectories_and_sample_coverage(self):
        counts = validate(self.review, {})
        self.assertEqual(counts['complete_episodes'], 3)
        self.assertEqual(counts['snapshots'], 17)
        self.assertEqual(counts['decisions'], 12)
        self.assertEqual(counts['facts'], 22)
        self.assertEqual(counts['facts_with_decision_trace'], 22)
        self.assertEqual(counts['facts_in_supervised_targets'], 19)

    def test_unmodified_v1_example(self):
        legacy = read_json(ROOT / 'examples' / 'synthetic-review.json')
        counts = validate(legacy, {})
        self.assertEqual(counts['complete_episodes'], 1)
        self.assertEqual(counts['snapshots'], 4)
        self.assertEqual(counts['fact_episodes'], 0)

    def test_premature_result(self):
        start = self.button['snapshots'][0]
        completed_press = self.button['snapshots'][2]['claims'][1]
        start['claims'].append(completed_press)
        start['memory'] += ' ' + completed_press['text']
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_unsampled_expired_state(self):
        self.button['snapshots'].pop(2)
        del self.button['decisions']
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_conflicting_current_states(self):
        conflicting = deepcopy(self.cover['facts'][3])
        conflicting.update(id='unexpected_visibility', value='fully_visible')
        self.cover['facts'].append(conflicting)
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_mislinked_reference_history(self):
        self.button['decisions'][-1]['previous_memory_frame'] = 2
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_unlinked_free_text(self):
        self.cover['snapshots'][0]['memory'] = 'The left block has been uncovered.'
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_unknown_linked_fact(self):
        self.cover['snapshots'][0]['claims'][0]['facts'] = ['invented_binding']
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_future_evidence_for_expiration(self):
        press = self.button['facts'][1]
        press['end_evidence'][0]['frame'] = press['end'] + 1
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_expiration_before_terminal_needs_evidence(self):
        del self.button['facts'][1]['end_evidence']
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_masked_decision_excluded_from_target_coverage(self):
        self.button['decisions'][1]['supervise_memory'] = False
        counts = validate(self.review, {})
        self.assertEqual(counts['facts_with_decision_trace'], 22)
        self.assertEqual(counts['facts_in_supervised_targets'], 18)

    def test_omitted_required_historical_result(self):
        terminal = self.button['snapshots'][-1]
        terminal['claims'].pop(1)
        terminal['memory'] = ' '.join(claim['text'] for claim in terminal['claims'])
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_required_fact_needs_snapshot_when_it_starts(self):
        self.cover['facts'].append({
            'id': 'left_mat_empty', 'kind': 'state', 'subject': 'left_mat',
            'predicate': 'occupancy', 'value': 'empty', 'start': 4, 'end': None,
            'evidence': [{'frame': 4, 'camera': 'head'}], 'required_in_memory': True,
        })
        for snapshot in self.cover['snapshots']:
            if snapshot['frame'] > 4:
                claim = {'text': 'The left mat is empty.', 'facts': ['left_mat_empty']}
                snapshot['claims'].append(claim)
                snapshot['memory'] += ' ' + claim['text']
        with self.assertRaises(ReviewError):
            validate(self.review, {})

    def test_partial_review_uses_exclusive_end(self):
        self.button['scope'] = 'partial'
        self.button['review_end'] = 2
        self.button['facts'] = self.button['facts'][:2]
        self.button['snapshots'] = self.button['snapshots'][:2]
        self.button['decisions'] = self.button['decisions'][:1]
        del self.button['stages']
        counts = validate(self.review, {})
        self.assertEqual(counts['partial_episodes'], 1)
        self.button['review_end'] = 3
        with self.assertRaises(ReviewError):
            validate(self.review, {})


if __name__ == '__main__':
    unittest.main()
