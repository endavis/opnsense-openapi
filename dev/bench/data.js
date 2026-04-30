window.BENCHMARK_DATA = {
  "lastUpdate": 1777573653743,
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
          "id": "4eebeb5d02728d7f617f5bbbce3bfb7b32e0b799",
          "message": "docs: dissolve mkdocs.yml 'Project' nav section (merges PR #19, addresses #16)\n\nPR #13 (template sync, addresses #12) preserved a \"Project\" catch-all\nnav section in mkdocs.yml containing four legacy top-level docs\n(ARCHITECTURE.md, HEURISTICS.md, GENERATED_CLIENT_USAGE.md,\nPUBLISHING.md). Issue #16 flagged that this diverged from the upstream\npyproject-template conventions: no upstream equivalent exists, the\nfilenames used PascalCase/snake_case in a kebab-case repo, and they\nlacked the YAML frontmatter that every sibling doc carries.\n\nPer the plan in #16, dissolve the section and redistribute the four\ndocs into upstream-style groups under their kebab-case names, each with\nthe standard frontmatter.\n\nFile moves (via git mv, history preserved — use git log --follow):\n- docs/ARCHITECTURE.md         -> docs/development/architecture.md\n- docs/HEURISTICS.md           -> docs/development/heuristics.md\n- docs/GENERATED_CLIENT_USAGE.md -> docs/usage/generated-client.md\n- docs/PUBLISHING.md           -> docs/deployment/publishing.md\n\nEach moved file gained YAML frontmatter (title/description/audience/\ntags) consistent with sibling docs in its new section.\n\nNav reorganization (mkdocs.yml):\n- Removed the 5-line \"Project\" catch-all section.\n- Appended Generated Client to Usage.\n- Inserted Architecture and Heuristics after Coding Standards in\n  Development.\n- Appended Publishing after Production in Deployment.\n\nInbound-reference fixes:\n- README.md line 87 — link rewritten to docs/usage/generated-client.md.\n- docs/development/heuristics.md line 672 — internal cross-link to the\n  architecture doc rewritten in relative form (./architecture.md) now\n  that both files live in the same directory.\n\ndocs/TABLE_OF_CONTENTS.md regenerated by the pre-commit hook.\n\ngit grep across the repo (excluding TABLE_OF_CONTENTS.md and CHANGELOG)\nreturns zero matches for the old filenames; no stale references remain.\n\nClosing the PR #13 follow-up trio:\n- #15 -> PR #17 (logging.py + benchmarks)\n- #14 -> PR #18 (docs/examples drift)\n- #16 -> this PR (Project nav section)\n\nThe per-file exclusion mechanism for tools/pyproject_template/check_\ntemplate_updates.py remains an open concern (first noted in PR #17)\nbut is not part of this trio.\n\nAddresses #16\n\nCo-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>",
          "timestamp": "2026-04-23T19:49:02+01:00",
          "tree_id": "70ed8d64108c3767ae3bd75abecc2bf84f10967d",
          "url": "https://github.com/endavis/opnsense-openapi/commit/4eebeb5d02728d7f617f5bbbce3bfb7b32e0b799"
        },
        "date": 1776970168616,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/test_bench_generator.py::test_bench_generate_spec",
            "value": 711.4834387359151,
            "unit": "iter/sec",
            "range": "stddev: 0.001977372461971123",
            "extra": "mean: 1.405514092888359 msec\nrounds: 689"
          },
          {
            "name": "tests/benchmarks/test_bench_parser.py::test_bench_parse_directory",
            "value": 1001.0340457820441,
            "unit": "iter/sec",
            "range": "stddev: 0.00018351343771384429",
            "extra": "mean: 998.9670223641233 usec\nrounds: 626"
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
          "id": "2757344f0c6ac955685c8a4b7744358ca699bbe3",
          "message": "chore: complete .envrc and .envrc.local.example sync (merges PR #22, addresses #21)\n\nchore: complete .envrc and .envrc.local.example sync from PR #13\n\nPR #13 (template sync, addresses #12) section 4 explicitly listed\n.envrc and .envrc.local.example for sync but the implementation\nskipped both. Gap discovered while preparing the v0.3.0 release.\n\n.envrc — replaced project's 4-line stub with upstream's 43-line\nversion verbatim (no project-specific content to preserve):\n\n- Auto-activate .venv with helpful \"run uv sync --all-extras --dev\"\n  hint when missing.\n- Redirect dev tool caches into tmp/: UV_CACHE_DIR, RUFF_CACHE_DIR,\n  MYPY_CACHE_DIR, COVERAGE_FILE, PRE_COMMIT_HOME.\n- source_env + watch_file .envrc.local so direnv reloads on edit.\n- Load diagnostics output and tip to create .envrc.local if missing.\n\n.envrc.local.example — merged. Preserved the OPNsense credentials\nblock (annotated \"NEVER commit these!\" inline) and appended upstream's\ngeneric examples: DEBUG/LOG_LEVEL toggles, cache overrides,\nEDITOR/BROWSER, ENABLE_LSP_TOOL=1 (pairs with .claude/lsp-setup.md\nadopted in PR #13), PYRIGHT_PYTHON_DEBUG=1. Dropped upstream's generic\nAPI_KEY/DATABASE_URL placeholders since the OPNsense block already\nserves the concrete-credentials role.\n\ndiff .envrc tmp/extracted/pyproject-template-main/.envrc returns clean.\n\nAddresses #21\n\nCo-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>",
          "timestamp": "2026-04-23T20:07:32+01:00",
          "tree_id": "d0fa5903e5cac122c6e0ef6577aa028c3024f613",
          "url": "https://github.com/endavis/opnsense-openapi/commit/2757344f0c6ac955685c8a4b7744358ca699bbe3"
        },
        "date": 1776971279916,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/test_bench_generator.py::test_bench_generate_spec",
            "value": 759.9414122712351,
            "unit": "iter/sec",
            "range": "stddev: 0.0014054391300809775",
            "extra": "mean: 1.3158909145526132 msec\nrounds: 749"
          },
          {
            "name": "tests/benchmarks/test_bench_parser.py::test_bench_parse_directory",
            "value": 1073.7729633212882,
            "unit": "iter/sec",
            "range": "stddev: 0.00003353340796967029",
            "extra": "mean: 931.2955663429065 usec\nrounds: 618"
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
          "id": "e229af5ecda2b93227ae794cc4a877b6cd7300ea",
          "message": "release: v0.3.0 (merges PR #23)\n\nchore: update changelog for v0.3.0",
          "timestamp": "2026-04-23T20:11:24+01:00",
          "tree_id": "cbaaaa90ce1e45df52593f4b16cbce88f0627edb",
          "url": "https://github.com/endavis/opnsense-openapi/commit/e229af5ecda2b93227ae794cc4a877b6cd7300ea"
        },
        "date": 1776971518060,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/test_bench_generator.py::test_bench_generate_spec",
            "value": 672.4287489347744,
            "unit": "iter/sec",
            "range": "stddev: 0.0027670595404557406",
            "extra": "mean: 1.4871464100607632 msec\nrounds: 656"
          },
          {
            "name": "tests/benchmarks/test_bench_parser.py::test_bench_parse_directory",
            "value": 1056.3467720954902,
            "unit": "iter/sec",
            "range": "stddev: 0.000047827092106949985",
            "extra": "mean: 946.6588306189318 usec\nrounds: 614"
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
          "id": "1a0f2e68f02636ff8596674cf87c2a74c157eb2f",
          "message": "fix: emit snake_case controller segments in generated URL paths (merges PR #36, addresses #32)\n\nOPNsense's Mvc/Router.php converts snake_case URL segments to CamelCase\ncontroller class names. The generator was emitting collapsed-lowercase\nsegments (vlansettings), which the router does not route. Use\nto_snake_case(controller) for the URL path so multi-word controllers\n(VlanSettings, OneToOne, HasyncStatus) produce routable paths.\n\nAddresses #32\n\nCo-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>",
          "timestamp": "2026-04-30T19:27:00+01:00",
          "tree_id": "4d637667b092106993519a76aebf9a1753655031",
          "url": "https://github.com/endavis/opnsense-openapi/commit/1a0f2e68f02636ff8596674cf87c2a74c157eb2f"
        },
        "date": 1777573653419,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/test_bench_generator.py::test_bench_generate_spec",
            "value": 667.9211162323131,
            "unit": "iter/sec",
            "range": "stddev: 0.002973806029451714",
            "extra": "mean: 1.4971827895499337 msec\nrounds: 689"
          },
          {
            "name": "tests/benchmarks/test_bench_parser.py::test_bench_parse_directory",
            "value": 1076.109096615372,
            "unit": "iter/sec",
            "range": "stddev: 0.000036523984238091537",
            "extra": "mean: 929.273809825831 usec\nrounds: 631"
          }
        ]
      }
    ]
  }
}