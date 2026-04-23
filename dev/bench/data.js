window.BENCHMARK_DATA = {
  "lastUpdate": 1776967334973,
  "repoUrl": "https://github.com/endavis/opnsense-openapi",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "email": "6662995+endavis@users.noreply.github.com",
            "name": "Eric Davis",
            "username": "endavis"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "0bcaee74470462eff33ebe1180541b126b124ee2",
          "message": "chore: adopt template logging.py and benchmarks scaffolding (merges PR #17, addresses #15)\n\nchore: adopt template logging and benchmarks scaffolding\n\nImplements the scoped plan from issue #15. Adopts only the upstream\ntemplate pieces that fill a real infrastructure gap; skips the toy\nscaffolding and pedagogical tests.\n\nAdopted from upstream (tmp/extracted/pyproject-template-main/):\n- src/opnsense_openapi/logging.py — verbatim copy of\n  src/package_name/logging.py with one prose substitution (docstring\n  package_name -> opnsense_openapi). Provides LogLevel,\n  SimpleConsoleFormatter, StructuredFileFormatter, setup_logging(),\n  get_logger(). Stdlib only.\n- tests/test_logging.py — 20 tests, import path rewritten to\n  opnsense_openapi.logging.\n- tests/benchmarks/__init__.py + conftest.py — empty package +\n  upstream docstring noting marker registration.\n\nProject-specific additions:\n- tests/benchmarks/test_bench_parser.py — benchmarks\n  ControllerParser.parse_directory() over a synthetic 8-controller\n  PHP tree.\n- tests/benchmarks/test_bench_generator.py — benchmarks\n  OpenApiGenerator.generate() over 6 synthetic in-memory\n  ApiController instances.\n\nCLI integration:\n- src/opnsense_openapi/cli.py — main() callback now accepts\n  --log-level (LogLevel | None) and --log-file (Path | None) and\n  calls setup_logging(level=log_level, log_file=log_file).\n\nDocumentation:\n- docs/reference/api.md — appended one mkdocstrings block for the\n  new opnsense_openapi.logging module.\n\nSkipped per plan (not deviations): src/package_name/core.py,\ntests/test_core.py, the Click-based tests/test_cli.py,\ntests/test_example.py, tests/benchmarks/test_bench_{core,logging}.py,\nand TestGreetProperties in tests/template/test_properties.py\n(omitted in PR #13; deferral now permanent).\n\nBehavior change: the 5 project modules using logger =\nlogging.getLogger(__name__) (generator, downloader, validator,\nclient/base, cli) were previously silent because no basicConfig()\nran. After this PR, the Typer callback runs setup_logging() on every\ninvocation, so existing logger.info() calls now produce console\noutput by default at INFO level. typer.echo() calls are unchanged.\n\nFollow-up: tools/pyproject_template/check_template_updates.py has no\nper-file exclusion mechanism, so future `manage.py check` runs will\nkeep flagging the deliberately-skipped files as drift. A separate\nissue should add a project-local exclusion list.\n\nAddresses #15\n\nCo-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>",
          "timestamp": "2026-04-23T18:02:41+01:00",
          "tree_id": "64b82ec21f8c66b27e90d67b6cf33fb6496e27bb",
          "url": "https://github.com/endavis/opnsense-openapi/commit/0bcaee74470462eff33ebe1180541b126b124ee2"
        },
        "date": 1776963793143,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/test_bench_generator.py::test_bench_generate_spec",
            "value": 601.3368947394046,
            "unit": "iter/sec",
            "range": "stddev: 0.003026788914165167",
            "extra": "mean: 1.6629613262518346 msec\nrounds: 659"
          },
          {
            "name": "tests/benchmarks/test_bench_parser.py::test_bench_parse_directory",
            "value": 1048.4536124868876,
            "unit": "iter/sec",
            "range": "stddev: 0.000025112056536763823",
            "extra": "mean: 953.7856401944597 usec\nrounds: 617"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "6662995+endavis@users.noreply.github.com",
            "name": "Eric Davis",
            "username": "endavis"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "f5b92a5af413b5c6a8308ac57ab3c5f5c7ab3015",
          "message": "chore: resolve docs/examples drift; skip upstream .py examples (merges PR #18, addresses #14)\n\nchore: resolve docs/examples drift from template sync\n\nPR #13's template sync brought in docs/examples/{README,api,add-a-feature}.md\nwith markers expanded, but those files describe code shapes that do not\nexist in this project (FastAPI service scaffolding, greet()/core.py\nwalkthrough). Per the plan attached to issue #14, formally skip the\nupstream .py examples and clean up the docs to honestly describe what\nthe project actually ships.\n\nDecision: skip upstream examples/api/, examples/advanced_usage.py,\nexamples/cli_usage.py, and upstream's examples/basic_usage.py\npermanently. The FastAPI scaffolding has no architectural fit for a\ncode-generator CLI; the example scripts target a generic-package shape.\nThe project's three OPNsense-specific scripts under examples/\n(basic_usage.py, diagnose_api.py, openapi_example.py) are correct\nas-is and remain unchanged.\n\nCleanup:\n- Rewrote docs/examples/README.md to honestly index the project's three\n  real scripts, with frontmatter shape preserved.\n- Deleted docs/examples/api.md (692-line FastAPI development guide).\n- Deleted docs/examples/add-a-feature.md (built around scaffolding\n  skipped in PR #17).\n- Removed inbound references in mkdocs.yml (2 nav entries),\n  docs/index.md (1 bullet), docs/usage/cli.md (1 link), and\n  docs/development/ai/first-5-minutes.md (1 TODO bullet, plus a stale\n  reference to upstream issue #342 that came along with it).\n- Regenerated docs/TABLE_OF_CONTENTS.md; 5 stale entries gone.\n\nPer-file exclusion follow-up (re-issued from PR #17):\ntools/pyproject_template/check_template_updates.py does not yet support\na project-local exclusion list. Until that mechanism lands, future\nmanage.py check runs will continue to flag the deliberately-skipped\nupstream files. The skip decisions are recorded in this PR and PRs\n#13/#17 rather than in tooling.\n\nAddresses #14\n\nCo-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>",
          "timestamp": "2026-04-23T19:01:47+01:00",
          "tree_id": "97801d82952b799a3871542d37cc6ffd00c036f5",
          "url": "https://github.com/endavis/opnsense-openapi/commit/f5b92a5af413b5c6a8308ac57ab3c5f5c7ab3015"
        },
        "date": 1776967334648,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/test_bench_generator.py::test_bench_generate_spec",
            "value": 701.8886146660558,
            "unit": "iter/sec",
            "range": "stddev: 0.0017784169900939431",
            "extra": "mean: 1.4247274839694892 msec\nrounds: 655"
          },
          {
            "name": "tests/benchmarks/test_bench_parser.py::test_bench_parse_directory",
            "value": 1056.3101133567752,
            "unit": "iter/sec",
            "range": "stddev: 0.00006210034302666509",
            "extra": "mean: 946.6916839621737 usec\nrounds: 636"
          }
        ]
      }
    ]
  }
}