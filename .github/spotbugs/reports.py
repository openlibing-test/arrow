from pathlib import Path
from collections import Counter
from urllib.parse import unquote
import argparse
import json
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--after-upload', action='store_true')
args = parser.parse_args()
source = Path('java-source')
evidence = Path('target/verification')
reports = evidence / 'reports'
reports.mkdir(exist_ok=True)
summary = {'phase': 'after-upload' if args.after_upload else 'before-upload', 'reports': [], 'coverage': dict(), 'snippet_mismatches': []}
coverage = Counter()
if not args.after_upload:
    native = sorted(source.glob('**/target/reports/spotbugs.sarif'))
    assert native, 'No reports at the documented filename/path'
    summary['root_report_exists'] = (source / 'target/reports/spotbugs.sarif').is_file()
    for path in native:
        name = path.relative_to(source).as_posix().replace('/', '__')
        raw = evidence / 'native-reports' / name
        raw.parent.mkdir(exist_ok=True)
        shutil.copy2(path, raw)
        shutil.copy2(path, reports / name)

for path in sorted(reports.glob('*.sarif')):
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['version'] == '2.1.0' and data['runs']
    module = source / path.name.split('__target__')[0].replace('__', '/')
    if path.name.startswith('target__'):
        module = source
    roots = [module / 'src/main/java', module / 'src/main/kotlin', module / 'target/generated-sources']
    files = [p for root in roots for p in root.rglob('*') if p.is_file()]
    def resolve(uri):
        uri = unquote(uri)
        direct = Path(uri.removeprefix('file://'))
        if direct.is_file():
            return direct
        matches = [p for p in files if p.as_posix().endswith('/' + uri)]
        assert len(matches) <= 1, f'Ambiguous source: {uri}'
        return matches[0] if matches else None
    def normalize(value):
        if isinstance(value, dict):
            if 'uri' in value:
                actual = resolve(value['uri'])
                if actual:
                    value['uri'] = actual.as_posix()
                    value.pop('uriBaseId', None)
            for child in value.values():
                normalize(child)
        elif isinstance(value, list):
            for child in value:
                normalize(child)
    if not args.after_upload:
        normalize(data)
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    results = [result for run in data['runs'] for result in run.get('results', [])]
    summary['reports'].append({'file': path.name, 'results': len(results), 'rules': len({r.get('ruleId') for r in results})})
    for result in results:
        for location in result.get('locations', []):
            physical = location['physicalLocation']
            actual = resolve(physical['artifactLocation']['uri'])
            region = physical.get('region', {})
            if not actual:
                coverage['unresolved_source'] += 1
                continue
            if not region.get('startLine'):
                coverage['missing_line'] += 1
                continue
            lines = actual.read_text(encoding='utf-8').splitlines()
            start = region['startLine']
            if start > len(lines):
                coverage['line_out_of_range'] += 1
                continue
            coverage['valid_source_line'] += 1
            if args.after_upload:
                expected = '\n'.join(lines[start-1:region.get('endLine', start)])
                if region.get('snippet', {}).get('text') != expected:
                    summary['snippet_mismatches'].append(f'{actual}:{start}')
                else:
                    coverage['correct_snippet'] += 1
summary['coverage'] = dict(coverage)
summary['results'] = sum(r['results'] for r in summary['reports'])
output = evidence / ('summary-after-upload.json' if args.after_upload else 'summary.json')
output.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, indent=2))
assert not summary['snippet_mismatches'], 'Missing/incorrect snippets for valid source lines'
