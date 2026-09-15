from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

import torch
from torch.nn import functional as F
from fold_lm.v05_benchmarks import gate_e_c149_margin_accounting as c149


def fp(head):
    digest = hashlib.sha256()
    for name,t in sorted(head.state_dict().items()):
        digest.update(name.encode()); digest.update(str(tuple(t.shape)).encode())
        digest.update(str(t.dtype).encode()); digest.update(t.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


class ToyHead(torch.nn.Module):
    def __init__(self, **config):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.eye(3))


class V05C149MarginAccountingTests(unittest.TestCase):
    def vectors(self):
        g = torch.Generator().manual_seed(73)  # Toy data only, no registered seed.
        return tuple(F.normalize(torch.randn(7,3,8,generator=g,dtype=torch.float64),dim=-1) for _ in range(3))

    def test_reconstruction_matches_direct_normalized_sum_cosine(self):
        a,e,r = self.vectors()
        d = c149._decompose(a,e,r)
        qn,en,rn = [F.normalize(t.sum(1),dim=-1) for t in (a,e,r)]
        expected = (qn*en).sum(1)-(qn*rn).sum(1)
        torch.testing.assert_close(d['reconstructed_margin'],expected,atol=1e-12,rtol=0)

    def test_diagonal_only_orthogonal_example(self):
        v = torch.eye(4,dtype=torch.float64)
        a,e,r = v[:3][None],v[:3][None],v[[3,1,2]][None]
        d = c149._decompose(a,e,r)
        self.assertAlmostEqual(d['same_factor'].item(),1/3)
        self.assertAlmostEqual(d['cross_factor'].item(),0)
        self.assertAlmostEqual(d['candidate_norm'].item(),0)

    def test_equal_candidate_norms_have_zero_norm_term(self):
        a,e,_ = self.vectors()
        r = e[:,[2,0,1]]
        d = c149._decompose(a,e,r)
        torch.testing.assert_close(d['candidate_norm'],torch.zeros(7,dtype=torch.float64),atol=1e-12,rtol=0)

    def test_expected_rival_swap_negates_all_contributions(self):
        a,e,r = self.vectors()
        x,y = c149._decompose(a,e,r),c149._decompose(a,r,e)
        for part in c149.PARTS+('reconstructed_margin',):
            torch.testing.assert_close(x[part],-y[part],atol=1e-12,rtol=0)

    def test_common_factor_permutation_preserves_partition(self):
        tensors = self.vectors()
        x,y = c149._decompose(*tensors),c149._decompose(*(t[:,[2,0,1]] for t in tensors))
        for part in c149.PARTS:
            torch.testing.assert_close(x[part],y[part],atol=1e-12,rtol=0)

    def test_query_only_permutation_changes_partition_not_total(self):
        a,e,r = self.vectors()
        x,y = c149._decompose(a,e,r),c149._decompose(a[:,[1,2,0]],e,r)
        torch.testing.assert_close(x['direct_margin'],y['direct_margin'],atol=1e-12,rtol=0)
        self.assertFalse(torch.allclose(x['same_factor'],y['same_factor']))

    def test_norm_term_matches_registered_symmetric_formula(self):
        a,e,r = self.vectors()
        d = c149._decompose(a,e,r)
        nE,nR,nQ = e.sum(1).norm(dim=-1),r.sum(1).norm(dim=-1),a.sum(1).norm(dim=-1)
        E = (a.sum(1)*e.sum(1)).sum(1); R = (a.sum(1)*r.sum(1)).sum(1)
        expected = .5*(1/nE-1/nR)*(E+R)/nQ
        torch.testing.assert_close(d['candidate_norm'],expected,atol=1e-12,rtol=0)
        self.assertTrue((d['candidate_norm'].abs()>1e-5).any())

    def test_dot_matrices_and_norms_are_saved(self):
        a,e,r = self.vectors()
        d = c149._decompose(a,e,r)
        torch.testing.assert_close(d['expected_unit_dot_matrix'],a @ e.transpose(-1,-2))
        torch.testing.assert_close(d['rival_unit_dot_matrix'],a @ r.transpose(-1,-2))
        self.assertEqual(tuple(d['expected_unit_dot_matrix'].shape),(7,3,3))

    def test_accounting_does_not_mutate_or_backpropagate(self):
        tensors = tuple(t.requires_grad_(True) for t in self.vectors())
        copies = [t.detach().clone() for t in tensors]
        d = c149._decompose(*tensors)
        for t,c in zip(tensors,copies):
            self.assertTrue(torch.equal(t,c)); self.assertIsNone(t.grad)
        self.assertTrue(all(not v.requires_grad for v in d.values()))

    def test_float32_unit_inputs_accumulate_in_float64(self):
        d = c149._decompose(*(t.float() for t in self.vectors()))
        self.assertEqual(d['reconstructed_margin'].dtype,torch.float64)
        torch.testing.assert_close(d['same_factor']+d['cross_factor']+d['candidate_norm'],d['direct_margin'],atol=1e-10,rtol=0)

    def test_zero_sum_and_nonunit_inputs_are_rejected(self):
        a,e,r = self.vectors()
        for invalid in (torch.zeros_like(a),2*a):
            with self.assertRaises(ValueError): c149._decompose(invalid,e,r)
        v=torch.tensor([[1.,0.],[-.5,3**.5/2],[-.5,-3**.5/2]],dtype=torch.float64)[None]
        with self.assertRaises(ValueError): c149._decompose(v,v,v)

    def test_nonfinite_and_shape_mismatch_rejected(self):
        a,e,r = self.vectors()
        for bad in (a[:0],a[:,:2],a[0],None):
            with self.assertRaises(ValueError): c149._decompose(bad,e,r)
        a[0,0,0]=float('nan')
        with self.assertRaises(ValueError): c149._decompose(a,e,r)

    def test_summary_null_error_means_for_perfect_source(self):
        cases=[dict(correct=True,reconstruction_error=0,**dict.fromkeys(c149.PARTS,0))]
        s=c149._diagnostic_summary(cases)
        self.assertEqual(s['errors'],0)
        self.assertEqual(s['error_term_means'],dict.fromkeys(c149.PARTS,None))

    def test_summary_counts_overlapping_adverse_terms(self):
        cases=[dict(correct=False,reconstruction_error=1e-7,same_factor=.2,cross_factor=-.1,candidate_norm=-.15)]
        s=c149._diagnostic_summary(cases)
        self.assertEqual(s['positive_same_factor_errors'],1)
        self.assertEqual(s['negative_cross_factor_errors'],1)
        self.assertEqual(s['negative_candidate_norm_errors'],1)

    def test_wrong_prerequisite_rejected_before_auditor(self):
        with self.assertRaises(ValueError): c149._validate_prior({}, {},None,None,None)

    def test_console_only_prerequisite_cannot_be_replayed(self):
        data=dict(experiment_id=c149.PRIOR_ID,commit_sha=c149.PRIOR_COMMIT,status='FAIL',
            diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
            evaluation_manifest_sha256=c149.MANIFEST_SHA,
            summary=dict(fresh_seeds=list(c149.SEEDS),evaluation_composition=c149.MODES[1],
                train_consistent_composition_gate_passed=False,paired_heads=24,train_steps=600,**c149.CONFIG,
                paired_initialization_verified=True,evaluation_weights_preserved=True,inference_oracle_used=False,
                runtime_path_exercised=False,evaluation_oov_count=0,composition_reference_match_rate=1.0),
            records='omitted; see summary.json')
        with self.assertRaisesRegex(ValueError,'Full ordered'): c149._validate_prior(data,{},None,None,None)

    def make_checkpoint(self, directory):
        head=ToyHead()
        seed,arm=c149.SEEDS[0],c149.ARMS[0]
        path=directory/f'seed-{seed}-{arm.lower()}.pt'
        payload=dict(state_dict=head.state_dict(),config=c149.CONFIG,vocabulary=['a','b'],
            training_composition=c149.MODES[0],inference_composition=c149.MODES[1],experiment_id=c149.PRIOR_ID)
        torch.save(payload,path)
        entry=dict(final_head_sha256=fp(head),checkpoint=dict(path=str(path),sha256=c149._sha(path),serialized_bytes=path.stat().st_size))
        return path,payload,entry

    def test_safe_checkpoint_reconstruction_and_frozen_weights(self):
        with tempfile.TemporaryDirectory() as name:
            d=Path(name);path,_,entry=self.make_checkpoint(d)
            head,actual=c149._load_head(d,c149.SEEDS[0],c149.ARMS[0],entry,['a','b'],'cpu',ToyHead,fp)
            self.assertEqual(path,actual);self.assertEqual(fp(head),entry['final_head_sha256'])
            self.assertFalse(head.training);self.assertTrue(all(not p.requires_grad for p in head.parameters()))

    def test_checkpoint_metadata_and_byte_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            d=Path(name);path,payload,entry=self.make_checkpoint(d)
            args=(d,c149.SEEDS[0],c149.ARMS[0],entry,['a','b'],'cpu',ToyHead,fp)
            with self.assertRaises(ValueError): c149._load_head(*args[:4],['wrong'],'cpu',ToyHead,fp)
            entry['final_head_sha256']='wrong'
            with self.assertRaises(ValueError): c149._load_head(*args)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError): c149._load_head(*args)

    def test_reuses_all_source_seeds_and_both_arms(self):
        self.assertEqual(c149.SEEDS,tuple(range(20261681,20261693)))
        self.assertEqual(c149.ARMS,('POOLED_TRAIN','COMPOSED_TRAIN'))
        self.assertEqual(c149.RECONSTRUCTION_ATOL,1e-5)


if __name__ == '__main__':
    torch.set_num_threads(2)
    unittest.main()
