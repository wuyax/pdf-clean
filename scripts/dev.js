import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

// Path to python executable in the virtual env
const isWindows = process.platform === 'win32';
const pythonBin = isWindows
  ? path.join(projectRoot, 'python-sidecar', 'venv', 'Scripts', 'python.exe')
  : path.join(projectRoot, 'python-sidecar', 'venv', 'bin', 'python');

console.log('\x1b[36m%s\x1b[0m', 'Starting Python Sidecar Backend...');
const backend = spawn(pythonBin, ['src/main.py'], {
  cwd: path.join(projectRoot, 'python-sidecar'),
  stdio: 'inherit',
});

console.log('\x1b[36m%s\x1b[0m', 'Starting Tauri Frontend...');
const frontend = spawn('npm', ['run', 'tauri', 'dev'], {
  cwd: projectRoot,
  stdio: 'inherit',
  shell: true,
});

// Clean up processes on exit
const cleanUp = () => {
  console.log('\n\x1b[31m%s\x1b[0m', 'Stopping all services...');
  backend.kill('SIGTERM');
  frontend.kill('SIGTERM');
  process.exit();
};

process.on('SIGINT', cleanUp);
process.on('SIGTERM', cleanUp);
process.on('exit', cleanUp);
