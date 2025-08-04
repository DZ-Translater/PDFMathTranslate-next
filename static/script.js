console.log('🔍 script.js loaded successfully');

// Global variables
let currentFile = null;
let currentFileId = null;
let currentTaskId = null;
let statusPollingInterval = null;
let availableLanguages = [];
let availableServices = [];

// DOM elements
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const removeFileBtn = document.getElementById('removeFile');
const uploadBtn = document.getElementById('uploadBtn');
const translateBtn = document.getElementById('translateBtn');
const cancelBtn = document.getElementById('cancelBtn');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const progressDetails = document.getElementById('progressDetails');
const resultsSection = document.getElementById('resultsSection');
const downloadMono = document.getElementById('downloadMono');
const downloadDual = document.getElementById('downloadDual');
const translationStats = document.getElementById('translationStats');

// Service and language selects
const serviceSelect = document.getElementById('service');
const langFromSelect = document.getElementById('langFrom');
const langToSelect = document.getElementById('langTo');
const pageRangeSelect = document.getElementById('pageRange');
const pageInput = document.getElementById('pageInput');
const engineSettings = document.getElementById('engineSettings');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 DOM loaded, checking elements...');
    console.log('uploadBtn element:', uploadBtn);
    console.log('fileInput element:', fileInput);
    console.log('uploadArea element:', uploadArea);
    
    // Ensure engine settings are hidden from the start
    if (engineSettings) {
        engineSettings.style.display = 'none';
        engineSettings.innerHTML = '';
    }
    
    initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    try {
        // Load available languages and services
        await Promise.all([
            loadLanguages(),
            loadServices()
        ]);
    } catch (error) {
        console.error('Failed to initialize app:', error);
        showError('应用程序数据加载失败，请刷新页面。');
    }
}

function setupEventListeners() {
    // File upload
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('drop', handleDrop);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    fileInput.addEventListener('change', handleFileSelect);
    removeFileBtn.addEventListener('click', removeFile);
    
    // Upload and translation
    uploadBtn.addEventListener('click', function() {
        console.log('🔍 Upload button clicked, disabled:', uploadBtn.disabled);
        uploadFile();
    });
    translateBtn.addEventListener('click', startTranslation);
    cancelBtn.addEventListener('click', cancelTranslation);
    
    // Settings
    pageRangeSelect.addEventListener('change', togglePageInput);
    serviceSelect.addEventListener('change', updateEngineSettings);
    
    // Range slider
    const shortLineSplitFactor = document.getElementById('shortLineSplitFactor');
    const shortLineSplitFactorValue = document.getElementById('shortLineSplitFactorValue');
    if (shortLineSplitFactor && shortLineSplitFactorValue) {
        shortLineSplitFactor.addEventListener('input', function() {
            shortLineSplitFactorValue.textContent = this.value;
        });
    }
    
    // Download buttons
    downloadMono.addEventListener('click', () => downloadFile('mono'));
    downloadDual.addEventListener('click', () => downloadFile('dual'));
    
    // Advanced settings checkboxes
    const enhanceCompatibility = document.getElementById('enhanceCompatibility');
    const skipClean = document.getElementById('skipClean');
    const disableRichTextTranslate = document.getElementById('disableRichTextTranslate');
    
    if (enhanceCompatibility) {
        enhanceCompatibility.addEventListener('change', function() {
            if (this.checked) {
                skipClean.checked = true;
                disableRichTextTranslate.checked = true;
                skipClean.disabled = true;
                disableRichTextTranslate.disabled = true;
            } else {
                skipClean.disabled = false;
                disableRichTextTranslate.disabled = false;
            }
        });
    }
}

// File handling
function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
}

function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
}

function handleFile(file) {
    console.log('🔍 handleFile called with:', file.name, file.size);
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showError('请选择PDF文件。');
        return;
    }
    
    if (file.size > 100 * 1024 * 1024) { // 100MB limit
        showError('文件大小必须小于100MB。');
        return;
    }
    
    currentFile = file;
    fileName.textContent = file.name;
    uploadArea.style.display = 'none';
    fileInfo.style.display = 'flex';
    uploadBtn.disabled = false;
    
    console.log('✅ Upload button enabled');
    
    // Reset states
    currentFileId = null;
    translateBtn.disabled = true;
    resetTranslationUI();
    
    // Auto upload the file
    uploadFile();
}

function removeFile() {
    currentFile = null;
    currentFileId = null;
    fileInput.value = '';
    uploadArea.style.display = 'block';
    fileInfo.style.display = 'none';
    uploadBtn.disabled = true;
    translateBtn.disabled = true;
    resetTranslationUI();
}

// API calls
async function loadLanguages() {
    try {
        const response = await fetch('/api/languages');
        if (!response.ok) throw new Error('加载语言列表失败');
        
        availableLanguages = await response.json();
        populateLanguageSelects();
    } catch (error) {
        console.error('Error loading languages:', error);
        throw error;
    }
}

async function loadServices() {
    try {
        const response = await fetch('/api/services');
        if (!response.ok) throw new Error('加载翻译服务失败');
        
        availableServices = await response.json();
        populateServiceSelect();
    } catch (error) {
        console.error('Error loading services:', error);
        throw error;
    }
}

function populateLanguageSelects() {
    // Clear existing options
    langFromSelect.innerHTML = '';
    langToSelect.innerHTML = '';
    
    // Add language options
    availableLanguages.forEach(lang => {
        const fromOption = new Option(lang.display_name, lang.display_name);
        const toOption = new Option(lang.display_name, lang.display_name);
        
        langFromSelect.appendChild(fromOption);
        langToSelect.appendChild(toOption);
    });
    
    // Set default values to match backend defaults
    langFromSelect.value = 'English';
    langToSelect.value = 'Simplified Chinese';
}

function populateServiceSelect() {
    serviceSelect.innerHTML = '';
    
    availableServices.forEach(service => {
        const option = new Option(service.name, service.name);
        serviceSelect.appendChild(option);
    });
    
    // Set default to gpt-4o-mini if available, otherwise use first service
    const defaultService = availableServices.find(s => s.name === 'gpt-4o-mini');
    if (defaultService) {
        serviceSelect.value = 'gpt-4o-mini';
    } else if (availableServices.length > 0) {
        serviceSelect.value = availableServices[0].name;
    }
    updateEngineSettings();
}

function updateEngineSettings() {
    // Clear engine settings and hide the section
    engineSettings.innerHTML = '';
    engineSettings.style.display = 'none';
    
    // No longer display service-specific configuration
}

function togglePageInput() {
    pageInput.style.display = pageRangeSelect.value === 'Range' ? 'block' : 'none';
}

// Step 1: Upload file
async function uploadFile() {
    if (!currentFile) {
        showError('请先选择PDF文件。');
        return;
    }
    
    try {
        // Disable UI
        uploadBtn.disabled = true;
        uploadBtn.textContent = '上传中...';
        
        // Create FormData for file upload
        const formData = new FormData();
        formData.append('file', currentFile);
        
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '文件上传失败');
        }
        
        const result = await response.json();
        currentFileId = result.file_id;
        
        // Update UI to show upload success
        uploadBtn.textContent = '✅ 上传成功';
        uploadBtn.classList.add('success');
        translateBtn.disabled = false;
        
        // Update step UI
        const uploadStep = document.getElementById('uploadStep');
        const translateStep = document.getElementById('translateStep');
        const translateStatus = document.getElementById('translateStatus');
        
        uploadStep.classList.remove('active');
        uploadStep.classList.add('completed');
        translateStep.classList.add('active');
        translateStatus.className = 'workflow-status success';
        translateStatus.textContent = `文件已上传：${result.filename} (${(result.size / 1024).toFixed(1)} KB) - 现在可以配置翻译参数并开始翻译`;
        
        showSuccess(`文件上传成功：${result.filename} (${(result.size / 1024).toFixed(1)} KB)`);
        
    } catch (error) {
        console.error('Upload error:', error);
        showError(`文件上传失败：${error.message}`);
        
        // Reset upload button
        uploadBtn.disabled = false;
        uploadBtn.textContent = '上传文件';
        uploadBtn.classList.remove('success');
    }
}

// Step 2: Start translation
async function startTranslation() {
    if (!currentFileId) {
        showError('请先上传PDF文件。');
        return;
    }
    
    try {
        // Disable UI
        translateBtn.disabled = true;
        translateBtn.textContent = '启动翻译中...';
        
        // Collect translation settings
        const requestData = collectTranslationSettings();
        
        const response = await fetch('/api/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_id: currentFileId,
                config: requestData
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '翻译失败');
        }
        
        const result = await response.json();
        currentTaskId = result.task_id;
        
        // Show progress section and start polling
        showTranslationProgress();
        startStatusPolling();
        
    } catch (error) {
        console.error('Translation error:', error);
        showError(`翻译失败：${error.message}`);
        resetTranslationUI();
    }
}

function collectTranslationSettings() {
    const settings = {
        service: serviceSelect.value,
        lang_from: langFromSelect.value,
        lang_to: langToSelect.value,
        page_range: pageRangeSelect.value,
        page_input: pageInput.value.trim() || null,
        threads: parseInt(document.getElementById('threads').value),
        no_mono: document.getElementById('noMono').value === 'true',
        no_dual: document.getElementById('noDual').value === 'true',
        dual_translate_first: document.getElementById('dualTranslateFirst').value === 'true',
        use_alternating_pages_dual: document.getElementById('useAlternatingPagesDual').value === 'true',
        watermark_output_mode: document.getElementById('watermarkMode').value,
        custom_system_prompt_input: document.getElementById('customSystemPrompt').value || null,
        min_text_length: parseInt(document.getElementById('minTextLength').value) || 10,
        rpc_doclayout: document.getElementById('rpcDoclayout').value.trim() || null,
        pool_max_workers: (() => {
            const value = parseInt(document.getElementById('poolMaxWorkers').value);
            return value > 0 ? value : null;
        })(),
        no_auto_extract_glossary: document.getElementById('noAutoExtractGlossary').value === 'true',
        primary_font_family: document.getElementById('primaryFontFamily').value,
        skip_clean: document.getElementById('skipClean').checked,
        disable_rich_text_translate: document.getElementById('disableRichTextTranslate').checked,
        enhance_compatibility: false, // Always false due to known issues
        split_short_lines: document.getElementById('splitShortLines').checked,
        short_line_split_factor: parseFloat(document.getElementById('shortLineSplitFactor').value),
        translate_table_text: document.getElementById('translateTableText').checked,
        skip_scanned_detection: document.getElementById('skipScannedDetection').checked,
        ocr_workaround: document.getElementById('ocrWorkaround').checked,
        auto_enable_ocr_workaround: document.getElementById('autoEnableOcrWorkaround').checked,
        max_pages_per_part: parseInt(document.getElementById('maxPagesPerPart').value) || 0,
        formular_font_pattern: document.getElementById('formularFontPattern').value.trim() || null,
        formular_char_pattern: document.getElementById('formularCharPattern').value.trim() || null,
        ignore_cache: document.getElementById('ignoreCache').checked,
        engine_settings: {}
    };
    
    // Collect engine-specific settings
    const selectedService = availableServices.find(s => s.name === serviceSelect.value);
    if (selectedService) {
        selectedService.fields.forEach(field => {
            const element = document.getElementById(field.name);
            if (element) {
                if (field.type.includes('bool')) {
                    settings.engine_settings[field.name] = element.checked;
                } else if (field.type.includes('int')) {
                    settings.engine_settings[field.name] = parseInt(element.value) || 0;
                } else {
                    settings.engine_settings[field.name] = element.value;
                }
            }
        });
    }
    
    return settings;
}

function showTranslationProgress() {
    progressSection.style.display = 'block';
    progressSection.classList.add('fade-in');
    cancelBtn.style.display = 'inline-block';
    resultsSection.style.display = 'none';
    
    // Reset progress
    progressFill.style.width = '0%';
    progressText.textContent = '开始翻译...';
    progressDetails.textContent = '';
}

function startStatusPolling() {
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
    }
    
    statusPollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/task/${currentTaskId}/status`);
            if (!response.ok) {
                throw new Error('获取任务状态失败');
            }
            
            const status = await response.json();
            updateProgress(status);
            
            if (status.status === 'completed') {
                clearInterval(statusPollingInterval);
                showResults(status);
            } else if (status.status === 'error' || status.status === 'cancelled') {
                clearInterval(statusPollingInterval);
                showError(status.error || '翻译失败');
                resetTranslationUI();
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }, 1000);
}

function updateProgress(status) {
    const progress = status.progress || 0;
    progressFill.style.width = `${progress}%`;
    
    // Display stage message with more details
    let stageText = status.stage || '处理中...';
    
    // Add stage progress if available
    if (status.stage_current && status.stage_total) {
        stageText += ` (${status.stage_current}/${status.stage_total})`;
    }
    
    progressText.textContent = stageText;
    
    // Display additional details
    let detailsText = '';
    
    if (status.part_index && status.total_parts && status.total_parts > 1) {
        detailsText = `第${status.part_index}/${status.total_parts}部分`;
    }
    
    // Add percentage
    if (progress > 0) {
        const percentText = `${progress.toFixed(1)}%`;
        detailsText = detailsText ? `${detailsText} - ${percentText}` : percentText;
    }
    
    progressDetails.textContent = detailsText;
}

async function cancelTranslation() {
    if (!currentTaskId) return;
    
    try {
        await fetch(`/api/task/${currentTaskId}/cancel`, { method: 'POST' });
        clearInterval(statusPollingInterval);
        resetTranslationUI();
        showError('翻译已被用户取消。');
    } catch (error) {
        console.error('Error cancelling translation:', error);
    }
}

function showResults(status) {
    const result = status.result;
    
    // Show results section
    resultsSection.style.display = 'block';
    resultsSection.classList.add('fade-in');
    
    // Configure download buttons with storage URLs if available
    if (result.mono_pdf_path) {
        downloadMono.style.display = 'inline-block';
        // Store storage URL if available
        if (result.storage && result.storage.mono && result.storage.mono.access_url) {
            downloadMono.dataset.storageUrl = result.storage.mono.access_url;
            downloadMono.dataset.downloadType = 'storage';
        } else {
            downloadMono.dataset.downloadType = 'api';
        }
    }
    if (result.dual_pdf_path) {
        downloadDual.style.display = 'inline-block';
        // Store storage URL if available
        if (result.storage && result.storage.dual && result.storage.dual.access_url) {
            downloadDual.dataset.storageUrl = result.storage.dual.access_url;
            downloadDual.dataset.downloadType = 'storage';
        } else {
            downloadDual.dataset.downloadType = 'api';
        }
    }
    
    // Show stats with storage info
    const storageInfo = result.storage ? 
        `<p class="storage-info">✅ 文件已上传到云存储，可快速下载</p>` : 
        '<p class="storage-info warning">⚠️ 使用本地下载（可能较慢）</p>';
    
    translationStats.innerHTML = `
        <h4>翻译完成！</h4>
        <p><strong>处理时间：</strong> ${result.total_seconds.toFixed(2)} 秒</p>
        <p><strong>单语PDF：</strong> ${result.mono_pdf_path ? '可下载' : '未生成'}</p>
        <p><strong>双语PDF：</strong> ${result.dual_pdf_path ? '可下载' : '未生成'}</p>
        ${storageInfo}
    `;
    
    // Hide progress and reset UI
    progressSection.style.display = 'none';
    cancelBtn.style.display = 'none';
    translateBtn.disabled = false;
    translateBtn.textContent = '开始翻译';
}

async function downloadFile(fileType) {
    if (!currentTaskId) return;
    
    try {
        const button = fileType === 'mono' ? downloadMono : downloadDual;
        const downloadType = button.dataset.downloadType;
        
        if (downloadType === 'storage' && button.dataset.storageUrl) {
            // Direct download from object storage
            const storageUrl = button.dataset.storageUrl;
            const a = document.createElement('a');
            a.href = storageUrl;
            a.download = `translated_${fileType}_${currentTaskId}.pdf`;
            a.target = '_blank'; // Open in new tab for better compatibility
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            showSuccess('正在从云存储下载，速度更快！');
        } else {
            // Fallback to API download
            const response = await fetch(`/api/task/${currentTaskId}/download/${fileType}`);
            if (!response.ok) {
                throw new Error('下载失败');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `translated_${fileType}_${currentTaskId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }
    } catch (error) {
        console.error('Download error:', error);
        showError('下载失败，请重试。');
    }
}

function resetTranslationUI() {
    translateBtn.disabled = !currentFileId;
    translateBtn.textContent = '开始翻译';
    cancelBtn.style.display = 'none';
    progressSection.style.display = 'none';
    resultsSection.style.display = 'none';
    downloadMono.style.display = 'none';
    downloadDual.style.display = 'none';
    
    // Clear download button data attributes
    downloadMono.removeAttribute('data-storage-url');
    downloadMono.removeAttribute('data-download-type');
    downloadDual.removeAttribute('data-storage-url');
    downloadDual.removeAttribute('data-download-type');
    
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
        statusPollingInterval = null;
    }
    
    currentTaskId = null;
}

// Utility functions
function showError(message) {
    // Remove existing error messages
    const existingErrors = document.querySelectorAll('.error');
    existingErrors.forEach(error => error.remove());
    
    // Create new error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;
    
    // Insert at the beginning of main content
    const main = document.querySelector('main');
    main.insertAdjacentElement('afterbegin', errorDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

function showSuccess(message) {
    // Remove existing success messages
    const existingSuccess = document.querySelectorAll('.success');
    existingSuccess.forEach(success => success.remove());
    
    // Create new success message
    const successDiv = document.createElement('div');
    successDiv.className = 'success';
    successDiv.textContent = message;
    
    // Insert at the beginning of main content
    const main = document.querySelector('main');
    main.insertAdjacentElement('afterbegin', successDiv);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (successDiv.parentNode) {
            successDiv.remove();
        }
    }, 3000);
}