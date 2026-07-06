import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

const pkgPath = path.join(projectRoot, 'package.json');
const cargoPath = path.join(projectRoot, 'src-tauri', 'Cargo.toml');

try {
  const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
  const version = pkg.version;

  let cargoContent = fs.readFileSync(cargoPath, 'utf8');
  
  const versionRegex = /(^\[package\](?:(?!^\[)[\s\S])*?\r?\nversion\s*=\s*")[^"]*(")/m;
  if (!versionRegex.test(cargoContent)) {
    throw new Error('Could not find the [package] version field in Cargo.toml');
  }

  // Replace version under [package] section
  const newCargoContent = cargoContent.replace(
    versionRegex,
    `$1${version}$2`
  );

  if (cargoContent !== newCargoContent) {
    fs.writeFileSync(cargoPath, newCargoContent, 'utf8');
    console.log(`\x1b[32m[Version Sync]\x1b[0m Synced Cargo.toml version to ${version}`);
  }
} catch (error) {
  console.error('\x1b[31m[Version Sync Error]\x1b[0m Failed to sync version:', error);
  process.exit(1);
}
