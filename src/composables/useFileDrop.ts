import { ref, onUnmounted } from 'vue';
import { listen } from '@tauri-apps/api/event';

export function useFileDrop() {
  const isDragging = ref(false);
  let dragCounter = 0;
  let isMounted = true;
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
    dragCounter = Math.max(0, dragCounter - 1);
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
      const uDrop = await listen('tauri://drag-drop', (event: any) => {
        isDragging.value = false;
        dragCounter = 0;

        const payload = event.payload as { paths: string[] } | null;
        const droppedPaths = payload?.paths;
        if (droppedPaths && droppedPaths.length > 0) {
          const pdfPaths = droppedPaths.filter(p => p.toLowerCase().endsWith('.pdf'));
          if (pdfPaths.length > 0) {
            onFilesDropped(pdfPaths);
          }
        }
      });
      if (!isMounted) {
        uDrop();
      } else {
        unlistenDrop = uDrop;
      }

      const uHover = await listen('tauri://drag-over', () => {
        isDragging.value = true;
      });
      if (!isMounted) {
        uHover();
      } else {
        unlistenHover = uHover;
      }

      const uCancel = await listen('tauri://drag-leave', () => {
        isDragging.value = false;
        dragCounter = 0;
      });
      if (!isMounted) {
        uCancel();
      } else {
        unlistenCancel = uCancel;
      }
    } catch (e) {
      console.error("Failed to setup drag listeners", e);
    }
  }

  onUnmounted(() => {
    isMounted = false;
    if (unlistenDrop) {
      unlistenDrop();
      unlistenDrop = null;
    }
    if (unlistenHover) {
      unlistenHover();
      unlistenHover = null;
    }
    if (unlistenCancel) {
      unlistenCancel();
      unlistenCancel = null;
    }
  });

  return {
    isDragging,
    onDragEnter,
    onDragLeave,
    onDrop,
    setupTauriDropListeners,
  };
}
