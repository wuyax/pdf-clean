export type QualityPreset = 'standard' | 'high' | 'max';

import { ref, watch, computed } from 'vue';
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
  const qualityPreset = ref<QualityPreset>(
    (localStorage.getItem('qualityPreset') as QualityPreset) || 'high'
  );
  const resolvedQuality = computed(() => {
    switch (qualityPreset.value) {
      case 'standard':
        return { dpi: 72, quality: 70 };
      case 'max':
        return { dpi: 300, quality: 90 };
      case 'high':
      default:
        return { dpi: 150, quality: 80 };
    }
  });
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
  watch(qualityPreset, (val) => {
    localStorage.setItem('qualityPreset', val);
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
    qualityPreset,
    resolvedQuality,
    selectCustomOutputDir,
    error,
  };
}
