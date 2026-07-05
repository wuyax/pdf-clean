import { ref, onUnmounted } from 'vue';
import { listen } from '@tauri-apps/api/event';

export function useFileDrop() {
  const isDragging = ref(false);
  let dragCounter = 0;
  let unlistenDrop: (() => void) | null = null;
  let unlistenHover: (() => void) | null = null;
  let unlistenCancel: (() => void) | null = null;

  function onDragEnter(e: DragEvent) {
    dragCounter++;
    if (e.dataTransfer?.types.includes('Files')) {
      isDragging.value = true;
    }
  }

  function onDragLeave() {
    dragCounter--;
    if (dragCounter === 0) {
      isDragging.value = false;
    }
  }

  function onDrop() {
    dragCounter = 0;
    isDragging.value = false;
  }

  async function setupTauriDropListeners(onFilesDropped: (paths: string[]) => void) {
    try {
      unlistenDrop = await listen('tauri://file-drop', (event: any) => {
        isDragging.value = false;
        dragCounter = 0;

        const droppedPaths = event.payload as string[];
        if (droppedPaths && droppedPaths.length > 0) {
          const pdfPaths = droppedPaths.filter(p => p.toLowerCase().endsWith('.pdf'));
          if (pdfPaths.length > 0) {
            onFilesDropped(pdfPaths);
          }
        }
      });

      unlistenHover = await listen('tauri://file-drop-hover', () => {
        isDragging.value = true;
      });

      unlistenCancel = await listen('tauri://file-drop-cancelled', () => {
        isDragging.value = false;
        dragCounter = 0;
      });
    } catch (e) {
      console.error("Failed to setup drag listeners", e);
    }
  }

  onUnmounted(() => {
    if (unlistenDrop) unlistenDrop();
    if (unlistenHover) unlistenHover();
    if (unlistenCancel) unlistenCancel();
  });

  return {
    isDragging,
    onDragEnter,
    onDragLeave,
    onDrop,
    setupTauriDropListeners,
  };
}
