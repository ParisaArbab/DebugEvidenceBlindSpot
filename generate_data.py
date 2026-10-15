"""Deterministically generate matched, synthetic debugging-evidence counterfactuals.

Every family has two worlds (A and B) with identical tail logs and candidate
root causes; exactly one decisive earlier diagnostic line differs. The blind
condition is intentionally not identifiable from the available observation.
"""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# id, test_name, A explanation, B explanation, A decisive line, B decisive line, shared failing trace
FAMILIES = [
 ('flask_route_collision','test_blueprint_route',
  'The endpoint was registered twice by the route decorator', 'The blueprint was registered twice during application setup',
  '[TRACE earlier] register_route endpoint=invoice.read count=2; blueprint_register_count=1',
  '[TRACE earlier] register_route endpoint=invoice.read count=1; blueprint_register_count=2',
  'E AssertionError: View function mapping is overwriting an existing endpoint'),
 ('sympy_display','test_nested_display',
  'A subclass inherited an incorrect string-display method', 'A custom printer dispatched to the wrong type handler',
  '[TRACE earlier] display resolution: inherited Printable.__str__ from parent; custom printer dispatch=expected',
  '[TRACE earlier] display resolution: inherited __str__=expected; custom printer dispatch=WrongHandler',
  'E AssertionError: actual rendered expression does not match expected'),
 ('django_forbidden','test_private_endpoint',
  'The request was missing the CSRF header', 'The authenticated session cookie had expired',
  '[TRACE earlier] csrf_header_present=false; session.valid=true',
  '[TRACE earlier] csrf_header_present=true; session.valid=false',
  'E AssertionError: response.status_code == 403, expected 200'),
 ('pandas_join_rows','test_customer_merge',
  'A join key contained duplicates in the right table', 'The join used inner instead of left semantics',
  '[TRACE earlier] right_table join_key_unique=false; join_mode=left',
  '[TRACE earlier] right_table join_key_unique=true; join_mode=inner',
  'E AssertionError: output row count differs from expected'),
 ('numpy_matrix','test_image_features',
  'The feature array was reshaped using the wrong axis', 'The feature array was transposed into the wrong channel order',
  '[TRACE earlier] resize_axis=0 (expected=1); channel_order=HWC (expected=HWC)',
  '[TRACE earlier] resize_axis=1 (expected=1); channel_order=CHW (expected=HWC)',
  'E ValueError: input tensor has incompatible dimensions'),
 ('async_cancel','test_consumer_task',
  'A parent task explicitly cancelled the worker', 'A local deadline timer cancelled the worker',
  '[TRACE earlier] cancellation_source=parent_task; deadline_exceeded=false',
  '[TRACE earlier] cancellation_source=deadline_timer; parent_cancelled=false',
  'E asyncio.exceptions.CancelledError: task cancelled'),
 ('database_migration','test_insert_order',
  'The migration was not applied in the active database', 'The query selected an incorrect database schema',
  '[TRACE earlier] migration_applied=false; active_schema=public (expected=public)',
  '[TRACE earlier] migration_applied=true; active_schema=archive (expected=public)',
  'E ProgrammingError: database operation failed'),
 ('pytest_fixture','test_client_state',
  'The fixture definition was outside pytest discovery paths', 'The test requested a misspelled fixture name',
  '[TRACE earlier] fixture_declared=client_state; discovered=false; requested=client_state',
  '[TRACE earlier] fixture_declared=client_state; discovered=true; requested=clinet_state',
  'E fixture lookup failed while setting up the test'),
 ('json_decoder','test_event_payload',
  'The payload contained a trailing comma', 'The payload contained a UTF-8 byte-order mark',
  '[TRACE earlier] first_bytes=7b226964; trailing_bytes=2c7d; encoding=utf8',
  '[TRACE earlier] first_bytes=efbbbf7b; trailing_bytes=227d; encoding=utf8-sig mismatch',
  'E JSONDecodeError: could not parse event payload'),
 ('service_auth','test_workspace_call',
  'The API token had expired', 'The request referenced the wrong cloud project',
  '[TRACE earlier] auth_token_expired=true; project_id_matches=true',
  '[TRACE earlier] auth_token_expired=false; project_id_matches=false',
  'E HTTPError: 403 Forbidden'),
 ('webhook_duplicate','test_single_event',
  'The sender retried delivery after a missing acknowledgement', 'The receiver had no idempotency check for repeated events',
  '[TRACE earlier] delivery_attempts=2; receiver_dedup_enabled=true',
  '[TRACE earlier] delivery_attempts=1; receiver_dedup_enabled=false; event_processed_twice=true',
  'E AssertionError: expected one action, observed two'),
 ('torch_cuda_memory','test_train_step',
  'The training batch size was increased beyond available memory', 'Old activations remained referenced between training steps',
  '[TRACE earlier] batch_size=256 (baseline=16); retained_activation_tensors=0',
  '[TRACE earlier] batch_size=16 (baseline=16); retained_activation_tensors=140',
  'E torch.cuda.OutOfMemoryError: CUDA out of memory'),
 ('tokenizer_alignment','test_patch_offsets',
  'The prompt was truncated before token-offset computation', 'Unexpected special tokens shifted all offset positions',
  '[TRACE earlier] truncation=true; inserted_special_tokens=0',
  '[TRACE earlier] truncation=false; inserted_special_tokens=3',
  'E AssertionError: predicted spans do not align with source code'),
 ('vector_index','test_nearest_neighbor',
  'The search index was built with an older embedding model', 'The online query used an incorrect embedding model',
  '[TRACE earlier] index_encoder_version=v1 (expected=v2); query_encoder_version=v2',
  '[TRACE earlier] index_encoder_version=v2 (expected=v2); query_encoder_version=v1',
  'E ValueError: vector dimensions do not match index configuration'),
 ('filesystem_write','test_write_report',
  'The container mounted the output folder as read-only', 'The process UID had no ownership or write permission',
  '[TRACE earlier] mount_flags=ro; effective_uid_owns_target=true',
  '[TRACE earlier] mount_flags=rw; effective_uid_owns_target=false; mode=0600',
  'E PermissionError: cannot write generated report'),
 ('time_conversion','test_event_order',
  'The comparison combined timezone-aware and timezone-naive values', 'The event timestamps mixed seconds and milliseconds',
  '[TRACE earlier] timezone_awareness=(naive,aware); units=(ms,ms)',
  '[TRACE earlier] timezone_awareness=(aware,aware); units=(s,ms)',
  'E AssertionError: chronological ordering of events is invalid'),
 ('ci_compiler','test_package_build',
  'The C++ compiler executable was missing from the runner image', 'The installed SDK version was incompatible with the build',
  '[TRACE earlier] compiler_found=false; sdk_version=13 (required=13)',
  '[TRACE earlier] compiler_found=true; sdk_version=11 (required=13)',
  'E BuildError: native extension compilation failed'),
 ('python_import','test_load_module',
  'A local module shadowed the intended installed package', 'The process executed under an outdated virtual environment',
  '[TRACE earlier] module_source=./json.py (unexpected); venv_python=.venv/bin/python (expected)',
  '[TRACE earlier] module_source=site-packages/json (expected); venv_python=/opt/old-venv/bin/python',
  'E ImportError: module lacks expected attribute'),
 ('api_pagination','test_export_records',
  'The pagination cursor reset after the first page', 'The loop limit allowed only one page to be fetched',
  '[TRACE earlier] cursor_page_2=cursor_page_1; max_pages=unlimited',
  '[TRACE earlier] cursor_page_2=next_cursor; max_pages=1',
  'E AssertionError: export returned fewer records than expected'),
 ('cache_stale','test_product_price',
  'Two different request inputs mapped to the same cache key', 'An override accidentally extended the cached data lifetime',
  '[TRACE earlier] cache_key_for_distinct_inputs=identical; ttl=60 (expected=60)',
  '[TRACE earlier] cache_key_for_distinct_inputs=distinct; ttl=86400 (expected=60)',
  'E AssertionError: service returned outdated value'),
 ('locale_sort','test_sort_names',
  'The sorting locale was configured incorrectly', 'An unstable sort reordered items with equal keys',
  '[TRACE earlier] locale=sv_SE (expected=en_US); stable_sort=true',
  '[TRACE earlier] locale=en_US (expected=en_US); stable_sort=false',
  'E AssertionError: sorted items appear in the wrong order'),
 ('gateway_timeout','test_api_response',
  'The backend worker queue was overloaded', 'The proxy read timeout was configured too aggressively',
  '[TRACE earlier] worker_queue_depth=2000; proxy_read_timeout=60s (expected=60s)',
  '[TRACE earlier] worker_queue_depth=0; proxy_read_timeout=2s (expected=60s)',
  'E HTTPError: 504 Gateway Timeout'),
 ('graph_edges','test_heterogeneous_gnn',
  'The data loader filtered out an edge type required by the task', 'The preprocessing transform dropped the reverse edges',
  '[TRACE earlier] loader_edge_types=[writes] (expected=[writes,cites]); reverse_edges=present',
  '[TRACE earlier] loader_edge_types=[writes,cites]; reverse_edges=missing (expected=present)',
  'E AssertionError: graph message passing produced invalid output'),
 ('agent_debugging','test_issue_repair',
  'A diagnostic stack frame was discarded during tool-output compression', 'The agent searched an outdated source-code snapshot',
  '[TRACE earlier] compressor.retained_frames=0 (needed=1); code_snapshot=current',
  '[TRACE earlier] compressor.retained_frames=5; code_snapshot=stale (expected=current)',
  'E AssertionError: automated patch did not fix failing test'),
]

assert len(FAMILIES) == len({x[0] for x in FAMILIES})

def build():
  cases=[]
  for family, test, a, b, ea, eb, common in FAMILIES:
    preamble=[f'$ pytest -q tests/test_regression.py::{test}',
              '========================= test session starts =========================',
              f'FAILED tests/test_regression.py::{test}']
    tail=[f'    app/service.py:127: in {test}', common, '==================== 1 failed, 14 passed in 0.9s ====================']
    noise=[f'INFO  boot: initialized diagnostic subsystem {i}' for i in range(1,8)]
    for variant,evidence in [('A',ea),('B',eb)]:
      cases.append({'case_id':f'{family}_{variant.lower()}', 'family_id':family, 'twin':variant,
       'candidate_A':a, 'candidate_B':b, 'gold':variant,
       'preamble':preamble, 'causal_line':evidence, 'tail':tail,
       'noise':noise,
       'decoy':'[AUTOMATED TRIAGE, UNVERIFIED] A static heuristic guessed candidate A; supporting trace is not available.'})
  return cases

def prompt_view(case, condition):
  pre=case['preamble']; tail=case['tail']; cause=case['causal_line']; noise=case['noise']
  if condition=='raw': return '\n'.join(pre+noise+[cause]+tail)
  if condition=='tail_only': return '\n'.join(pre+tail)
  if condition=='cause_preserved': return '\n'.join(pre+[cause]+tail)
  if condition=='decoy_only': return '\n'.join(pre+[case['decoy']]+tail)
  if condition=='restored': return '\n'.join(pre+tail+['[RETRIEVED ORIGINAL DIAGNOSTIC LINE]',cause])
  raise ValueError(condition)

def main():
  ROOT.joinpath('data').mkdir(exist_ok=True)
  cases=build()
  path=ROOT/'data'/'paired_cases.jsonl'
  with path.open('w') as f:
    for item in cases: f.write(json.dumps(item,ensure_ascii=False)+'\n')
  manifest={'dataset':'Causal Evidence Deletion (CED) v1','synthetic':True,
   'family_count':len(FAMILIES),'case_count':len(cases), 'pairing':'24 matched A/B twin families',
   'conditions':['raw','tail_only','cause_preserved','decoy_only','restored'],
   'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
   'model_results_collected':False}
  (ROOT/'data'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  print('Generated',len(cases),'cases across',len(FAMILIES),'matched pairs')
  print('SHA256',manifest['sha256'])

if __name__=='__main__': main()
