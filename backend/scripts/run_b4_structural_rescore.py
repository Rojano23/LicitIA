"""Only Phase 3B: approved Golden + immutable stored structure + offline test replay."""
from __future__ import annotations
import argparse,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.document_intelligence_structural_rescore import load_golden,rescore,canonical_bytes
from app.document_intelligence_calibration_replay import read_batch,replay_batch

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url',default=os.environ.get('DATABASE_URL'))
    parser.add_argument('--output-json',type=Path,default=ROOT/'reports'/'di_r4a_b4_structure_rescore.json')
    parser.add_argument('--phase4',action='store_true',help='Evaluate structural trust hardening into a separate Phase 4 report')
    args=parser.parse_args(argv)
    expected_output=ROOT/'reports'/('di_r4a_b4_structure_phase4_rescore.json' if args.phase4 else 'di_r4a_b4_structure_rescore.json')
    if args.phase4 and args.output_json == ROOT/'reports'/'di_r4a_b4_structure_rescore.json':
        args.output_json=expected_output
    if args.output_json.resolve()!=expected_output.resolve():
        raise ValueError('Dedicated output only; original results cannot be overwritten')
    golden_path=ROOT/'evals'/'document_intelligence_b4_structure_golden_v1.json'
    result_path=ROOT/'reports'/'di_r4a_vision_b4_p1_p3_structure.json'
    before={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in (golden_path,result_path)}
    golden=load_golden(golden_path)
    observations=read_batch([result_path])
    replay=replay_batch(observations,args.database_url)
    report=rescore(golden,observations,replay)
    report.update(golden_file_sha256=before[golden_path],input_result_sha256=before[result_path],
        approval_revision=golden.approval_revision,
        recommended_next_action='ARCHITECT_REVIEW' if args.phase4 else 'D_PRODUCTION_ARCHITECTURE_CORRECTION',
        production_code_changed=args.phase4)
    if any(hashlib.sha256(path.read_bytes()).hexdigest()!=value for path,value in before.items()):
        raise RuntimeError('Immutable input changed during rescore')
    args.output_json.write_bytes(canonical_bytes(report))
    print(json.dumps(report['aggregate'],indent=2,sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
