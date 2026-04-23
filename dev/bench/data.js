window.BENCHMARK_DATA = {
  "lastUpdate": 1776963793921,
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
      }
    ]
  }
}