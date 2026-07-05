import { ref, watch } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { SaveMode, ConflictPolicy } from '../types/task';

export function useSettings() {
  const saveMode = ref<SaveMode>(
    (localStorage.getItem('saveMode') as SaveMode) || 'same-dir'
  );
  const customOutputDir = ref<string>(localStorage.getItem('customOutputDir') || '');
  const conflictPolicy = ref<ConflictPolicy>(
    (localStorage.getItem('conflictPolicy') as ConflictPolicy) || 'overwrite'
  );
  const error = ref('');

  watch(saveMode, (val) => {
    localStorage.setItem('saveMode', val);
  });
  watch(customOutputDir, (val) => {
    localStorage.setItem('customOutputDir', val);
  });
  watch(conflictPolicy, (val) => {
    localStorage.setItem('conflictPolicy', val);
  });

  async function selectCustomOutputDir() {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
      });
      if (selected && typeof selected === 'string') {
        customOutputDir.value = selected;
      }
    } catch (err) {
      error.value = '选择文件夹失败';
    }
  }

  return {
    saveMode,
    customOutputDir,
    conflictPolicy,
    selectCustomOutputDir,
    error,
  };
}
