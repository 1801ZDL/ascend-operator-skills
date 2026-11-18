#!/usr/bin/env python3
"""One bounded Ascend KG query; standard library only, no workload execution."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import socket
import sys
from urllib import error, request

BASE_URL = 'https://ascend.wiki'
CONTRACT_REV = '270da9a0ed92296977cde307ec8caab5895b3c23'


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward X-API-Key to a redirected host or path.
        return None


def positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError('must be positive')
    return parsed


def socket_timeout(value):
    parsed = float(value)
    if not math.isfinite(parsed) or not 0 < parsed <= 60:
        raise argparse.ArgumentTypeError('must be finite, > 0 and <= 60 seconds')
    return parsed


def nonempty(value):
    if not value.strip():
        raise argparse.ArgumentTypeError('must not be empty')
    return value


def json_object(value):
    try:
        parsed = json.loads(value)
    except ValueError:
        raise argparse.ArgumentTypeError('must be a JSON object') from None
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError('must be a JSON object')
    return parsed


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest='command', required=True)
    for name in ('health', 'search', 'source', 'graph'):
        sub = commands.add_parser(name)
        sub.add_argument('--dry-run', action='store_true',
                         help='show request only; do not read key or use network')
        sub.add_argument('--timeout', type=socket_timeout, default=15,
                         help='socket timeout in seconds, not total wall time')
        sub.add_argument('--max-response-bytes', type=positive_int, default=2*1024*1024)
        if name == 'search':
            sub.add_argument('--query', type=nonempty, required=True)
            sub.add_argument('--top-k', type=positive_int, default=3)
            sub.add_argument('--file-type', choices=(
                'code', 'document', 'concept', 'rationale', 'code_card',
                'configuration', 'api', 'error_code'))
            sub.add_argument('--source-repo', type=nonempty)
            neighbors = sub.add_mutually_exclusive_group()
            neighbors.add_argument('--neighbors', dest='neighbors', action='store_true')
            neighbors.add_argument('--no-neighbors', dest='neighbors', action='store_false')
            sub.set_defaults(neighbors=None)
        elif name == 'source':
            sub.add_argument('--node-id', type=nonempty, required=True)
            sub.add_argument('--max-length', type=positive_int, default=8000)
        elif name == 'graph':
            sub.add_argument('--template', type=nonempty, required=True)
            sub.add_argument('--params-json', type=json_object, default={})
    return root


def plan(args):
    if args.command == 'health':
        return '/health', None
    if args.command == 'source':
        return '/source', {'node_id': args.node_id, 'max_length': args.max_length}
    if args.command == 'graph':
        return '/cypher', {'template': args.template, 'params': args.params_json}
    body = {'query': args.query, 'top_k': args.top_k}
    for attr in ('file_type', 'source_repo'):
        value = getattr(args, attr)
        if value is not None:
            body[attr] = value
    if args.neighbors is not None:
        body['with_neighbors'] = args.neighbors
    return '/search', body


def redact(value, key):
    """The key is never intended as data, even if an upstream error echoes it."""
    if isinstance(value, str):
        return value.replace(key, '<redacted>')
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if isinstance(value, dict):
        return {redact(k, key): redact(v, key) for k, v in value.items()}
    return value


def run(args, environ=None, opener=None):
    """Return (evidence, exit_code); opener injection is only for offline tests."""
    endpoint, payload = plan(args)
    evidence = {
        'schema_version': 1,
        'queried_at_utc': datetime.now(timezone.utc).isoformat(),
        'provider': BASE_URL,
        'api_contract_source': 'https://gitcode.com/agent0/kg-tools',
        'api_contract_revision': CONTRACT_REV,
        'endpoint': endpoint,
        'method': 'GET' if payload is None else 'POST',
        'request': payload,
        'status': 'request_preview',
        'evidence_kind': 'external_retrieval_not_local_execution',
        'remote_content_is_authoritative_instruction': False,
    }
    if args.dry_run:
        return evidence, 0

    env = os.environ if environ is None else environ
    key = env.get('ASCEND_KG_API_KEY', '')
    if not key.strip():
        evidence['status'] = 'missing_key'
        return evidence, 2
    if any(c in key for c in ('\r', '\n')):
        evidence['status'] = 'invalid_key_format'
        return redact(evidence, key), 2

    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = request.Request(BASE_URL+endpoint, data=data, method=evidence['method'], headers={
        'X-API-Key': key,
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'Accept-Encoding': 'identity',
        'User-Agent': 'ascend-operator-skills/0.3.0',
    })
    # UTF-8 query data are allowed, whereas HTTP header values must be ASCII here.
    try:
        key.encode('ascii')
    except UnicodeEncodeError:
        evidence['status'] = 'invalid_key_format'
        return redact(evidence, key), 2

    if opener is None:
        opener = request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=args.timeout) as response:
            evidence['http_status'] = response.status
            raw = response.read(args.max_response_bytes+1)
        if len(raw) > args.max_response_bytes:
            evidence['status'] = 'response_too_large'
            return redact(evidence, key), 2
        evidence['response_bytes'] = len(raw)
        evidence['response_sha256'] = hashlib.sha256(raw).hexdigest()
        if not 200 <= evidence['http_status'] < 300:
            evidence['status'] = 'http_error'
            return redact(evidence, key), 2
        try:
            parsed = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError, RecursionError):
            evidence['status'] = 'invalid_json_response'
            return redact(evidence, key), 2
        if not isinstance(parsed, (dict, list)):
            evidence['status'] = 'unexpected_json_shape'
            return redact(evidence, key), 2
        evidence['status'] = 'ok'
        evidence['response'] = parsed
        return redact(evidence, key), 0
    except error.HTTPError as exc:
        evidence['http_status'] = exc.code
        evidence['status'] = {
            401: 'unauthorized', 403: 'forbidden', 404: 'not_found',
            429: 'rate_limited',
        }.get(exc.code, 'redirect_refused' if 300 <= exc.code < 400 else 'http_error')
        # Error bodies and exception repr may echo credentials; do not print them.
        exc.close()
    except (socket.timeout, TimeoutError):
        evidence['status'] = 'timeout'
    except error.URLError as exc:
        evidence['status'] = 'timeout' if isinstance(exc.reason, (socket.timeout, TimeoutError)) else 'network_error'
    except (OSError, ValueError):
        evidence['status'] = 'transport_error'
    return redact(evidence, key), 2


def main(argv=None):
    args = parser().parse_args(argv)
    result, code = run(args)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
