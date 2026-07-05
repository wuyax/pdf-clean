<template>
  <div class="flex-1 flex flex-col items-center justify-center pointer-events-none animate-in fade-in zoom-in duration-700">
    <div class="relative mb-6">
      <div class="absolute inset-0 bg-blue-100 rounded-full blur-3xl opacity-30 animate-pulse"></div>
      <div class="relative w-20 h-20 bg-slate-50 rounded-2xl border border-slate-100 flex items-center justify-center shadow-sm">
        <svg class="w-10 h-10 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      </div>
    </div>
    <p class="text-[15px] font-semibold text-slate-700 tracking-tight">准备好处理您的文档</p>
    <p class="text-xs text-slate-400 mt-2 font-medium">将 PDF 文件拖放到此处或点击“添加文件”</p>
  </div>
</template>
