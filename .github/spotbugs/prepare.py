from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

root = Path('java-source')
evidence = Path('target/verification')
evidence.mkdir(parents=True, exist_ok=True)
(evidence / 'source-commit.txt').write_text(subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True), encoding='utf-8')
pom = root / 'pom.xml'
(evidence / 'original-pom.xml').write_bytes(pom.read_bytes())
ns = 'http://maven.apache.org/POM/4.0.0'
ET.register_namespace('', ns)
q = lambda name: f'{{{ns}}}{name}'
tree = ET.parse(pom)
project = tree.getroot()
properties = project.find(q('properties'))
for key, value in {'spotbugs.version': '4.10.2', 'spotbugs-maven-plugin.version': '4.9.8.3', 'findsecbugs.version': '1.14.0'}.items():
    ET.SubElement(properties, q(key)).text = value
plugins = project.find(f"{q('build')}/{q('plugins')}")
plugin = ET.SubElement(plugins, q('plugin'))
for name, value in [('groupId', 'com.github.spotbugs'), ('artifactId', 'spotbugs-maven-plugin'), ('version', '${spotbugs-maven-plugin.version}')]:
    ET.SubElement(plugin, q(name)).text = value
dependencies = ET.SubElement(plugin, q('dependencies'))
for group, artifact, version in [('com.github.spotbugs', 'spotbugs', '${spotbugs.version}'), ('com.h3xstream.findsecbugs', 'findsecbugs-plugin', '${findsecbugs.version}')]:
    dependency = ET.SubElement(dependencies, q('dependency'))
    for name, value in [('groupId', group), ('artifactId', artifact), ('version', version)]:
        ET.SubElement(dependency, q(name)).text = value
configuration = ET.SubElement(plugin, q('configuration'))
# Optional include filter is deliberately omitted: analyze all default rules.
for name, value in [('failOnError', 'true'), ('effort', 'Max'), ('sarifOutput', 'true'), ('sarifOutputDirectory', '${project.build.directory}/reports'), ('sarifOutputFilename', 'spotbugs.sarif')]:
    ET.SubElement(configuration, q(name)).text = value
tree.write(pom, encoding='utf-8', xml_declaration=True)
(evidence / 'configured-pom.xml').write_bytes(pom.read_bytes())
print('Configured guide versions and SARIF options in Arrow Java root POM; inherited by Maven modules.')
