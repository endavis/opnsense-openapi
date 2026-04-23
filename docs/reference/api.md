---
title: API Reference
description: Complete API documentation for opnsense-openapi
audience:
  - users
  - contributors
tags:
  - reference
  - api
---

# API Reference

Complete API documentation for `opnsense-openapi`, auto-generated from source docstrings.

## Package Overview

::: opnsense_openapi
    options:
      show_root_heading: false
      show_source: false
      members: false

## Client

High-level HTTP client for talking to an OPNsense box.

::: opnsense_openapi.client
    options:
      show_root_heading: true
      show_root_full_path: true

## Specs

Helpers for locating bundled OpenAPI specs by OPNsense version.

::: opnsense_openapi.specs
    options:
      show_root_heading: true
      show_root_full_path: true

## Validator

Runtime validation of generated clients against bundled specs.

::: opnsense_openapi.validator
    options:
      show_root_heading: true
      show_root_full_path: true

## Parser

Controller XML parsing used to derive API surface.

::: opnsense_openapi.parser
    options:
      show_root_heading: true
      show_root_full_path: true

## Generator

OpenAPI spec + client code generation.

::: opnsense_openapi.generator
    options:
      show_root_heading: true
      show_root_full_path: true

## Downloader

Downloads upstream OPNsense source archives used during spec generation.

::: opnsense_openapi.downloader
    options:
      show_root_heading: true
      show_root_full_path: true

## Logging

Centralized logging configuration shared by the CLI and library code.

::: opnsense_openapi.logging
    options:
      show_root_heading: true
      show_root_full_path: true
