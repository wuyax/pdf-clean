<!-- src/App.vue -->
<template>
  <div class="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4">
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-md">
      <h1 class="text-2xl font-bold mb-6 text-center text-gray-800">PDF OCR Cleaner</h1>
      
      <div 
        class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:bg-gray-50 transition"
        @click="selectFile"
      >
        <p v-if="!selectedFile" class="text-gray-500">Click to select PDF</p>
        <p v-else class="text-green-600 font-medium">{{ selectedFile }}</p>
      </div>
      
      <div class="mt-6">
        <button 
          @click="processFile" 
          :disabled="!selectedFile || isProcessing"
          class="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isProcessing ? 'Processing...' : 'Clean PDF' }}
        </button>
      </div>
      
      <div v-if="error" class="mt-4 p-3 bg-red-100 text-red-700 rounded">
        {{ error }}
      </div>
      
      <div v-if="successPath" class="mt-4 p-3 bg-green-100 text-green-700 rounded text-sm break-all">
        Success! Saved to:<br> {{ successPath }}
        <button 
          @click="openFile" 
          class="mt-2 w-full bg-green-600 text-white py-1 px-3 rounded hover:bg-green-700 transition text-xs font-medium"
        >
          Open File
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { fetch } from '@tauri-apps/plugin-http';
import { openPath } from '@tauri-apps/plugin-opener';

const selectedFile = ref('');
const isProcessing = ref(false);
const error = ref('');
const successPath = ref('');

const API_URL = 'http://127.0.0.1:8000';

async function selectFile() {
  try {
    const file = await open({
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
      multiple: false,
    });
    if (file && typeof file === 'string') {
      selectedFile.value = file;
      error.value = '';
      successPath.value = '';
    }
  } catch (err) {
    error.value = 'Failed to select file';
  }
}

async function openFile() {
  if (successPath.value) {
    try {
      await openPath(successPath.value);
    } catch (err: any) {
      error.value = `Failed to open file: ${err.message}`;
    }
  }
}

async function processFile() {
  if (!selectedFile.value) return;
  
  isProcessing.value = true;
  error.value = '';
  successPath.value = '';
  
  try {
    const lastSlash = Math.max(selectedFile.value.lastIndexOf('/'), selectedFile.value.lastIndexOf('\\'));
    const outputDir = selectedFile.value.substring(0, lastSlash);

    const response = await fetch(`${API_URL}/process`, {
      method: 'POST',
      body: JSON.stringify({
        input_path: selectedFile.value,
        output_dir: outputDir
      }),
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      const data = await response.json() as any;
      successPath.value = data.output_path;
    } else {
      error.value = `Server Error: ${response.status}`;
    }
  } catch (err: any) {
    error.value = `Error: ${err.message}`;
  } finally {
    isProcessing.value = false;
  }
}
</script>
