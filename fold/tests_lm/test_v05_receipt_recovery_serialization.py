import json
import unittest

from fold_lm.v05.receipt_recovery import ReceiptRecoverySnapshot


class V05ReceiptRecoverySerializationTests(unittest.TestCase):
    def test_snapshot_json_roundtrip_preserves_state(self):
        snapshot = ReceiptRecoverySnapshot(
            pending_receipt_ids=frozenset(("p2", "p1")),
            completed_receipt_ids=frozenset(("c1",)),
        )
        payload = json.loads(json.dumps(snapshot.to_payload()))
        self.assertEqual(ReceiptRecoverySnapshot.from_payload(payload), snapshot)

    def test_invalid_snapshot_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            ReceiptRecoverySnapshot.from_payload({"pending_receipt_ids": []})


if __name__ == "__main__":
    unittest.main()
