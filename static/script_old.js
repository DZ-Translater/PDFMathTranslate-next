// Global variables
let currentFile = null;
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
    
    // Translation
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
    translateBtn.disabled = false;
}

function removeFile() {
    currentFile = null;
    fileInput.value = '';
    uploadArea.style.display = 'block';
    fileInfo.style.display = 'none';
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
    
    if (availableServices.length > 0) {
        serviceSelect.value = availableServices[0].name;
        updateEngineSettings();
    }
}

function updateEngineSettings() {
    const selectedService = availableServices.find(s => s.name === serviceSelect.value);
    engineSettings.innerHTML = '';
    
    if (selectedService && selectedService.fields.length > 0) {
        engineSettings.style.display = 'block';
        
        const title = document.createElement('h3');
        title.textContent = `${selectedService.name} 配置`;
        engineSettings.appendChild(title);
        
        selectedService.fields.forEach(field => {
            const group = document.createElement('div');
            group.className = 'settings-group';
            
            const label = document.createElement('label');
            label.textContent = field.description;
            label.setAttribute('for', field.name);
            
            let input;
            
            if (field.name === 'env_status') {
                // Special handling for environment variable status
                const statusDiv = document.createElement('div');
                statusDiv.className = 'env-status';
                
                const envStatus = field.default || {};
                Object.entries(envStatus).forEach(([envVar, isSet]) => {
                    const statusItem = document.createElement('div');
                    statusItem.className = `env-item ${isSet ? 'env-success' : 'env-warning'}`;
                    statusItem.innerHTML = `
                        <span class="env-var">${envVar}</span>: 
                        <span class="env-value">${isSet ? '✅ 已配置' : '❌ 未配置'}</span>
                    `;
                    statusDiv.appendChild(statusItem);
                });
                
                if (Object.values(envStatus).some(v => !v)) {
                    const warning = document.createElement('div');
                    warning.className = 'env-warning';
                    warning.textContent = '⚠️ 请通过环境变量配置API密钥和Base URL';
                    statusDiv.appendChild(warning);
                }
                
                group.appendChild(label);
                group.appendChild(statusDiv);
            } else if (field.readonly) {
                // Read-only field
                input = document.createElement('input');
                input.type = 'text';
                input.value = field.default || '';
                input.readOnly = true;
                input.className = 'readonly-input';
                input.id = field.name;
                input.name = field.name;
                
                group.appendChild(label);
                group.appendChild(input);
            } else {
                // Regular input field
                if (field.type.includes('bool')) {
                    input = document.createElement('input');
                    input.type = 'checkbox';
                    input.checked = field.default === true || field.default === 'true';
                } else {
                    input = document.createElement('input');
                    input.type = field.is_password ? 'password' : 'text';
                    input.value = field.default || '';
                    if (field.type.includes('int')) {
                        input.type = 'number';
                    }
                }
                
                input.id = field.name;
                input.name = field.name;
                
                group.appendChild(label);
                group.appendChild(input);
            }
            
            engineSettings.appendChild(group);
        });
    } else {
        engineSettings.style.display = 'none';
    }
}

function togglePageInput() {
    pageInput.style.display = pageRangeSelect.value === 'Range' ? 'block' : 'none';
}

// Translation process
async function startTranslation() {
    console.log('🚀 startTranslation called - DEBUG VERSION 2');
    
    if (!currentFile) {
        showError('请先选择PDF文件。');
        return;
    }
    
    try {
        // Disable UI
        translateBtn.disabled = true;
        translateBtn.textContent = '上传文件中...';
        
        // Step 1: Upload file
        const fileId = await uploadFile();
        
        // Step 2: Start translation
        translateBtn.textContent = '启动翻译中...';
        const requestData = collectTranslationSettings();
        
        // Debug logging
        console.log('🔍 File ID:', fileId);
        console.log('🔍 Config data keys:', Object.keys(requestData));
        console.log('🔍 Config data preview:', JSON.stringify(requestData).substring(0, 200));
        
        // Check if currentFile is accidentally included
        console.log('🔍 currentFile variable:', currentFile ? 'File object present' : 'null');
        
        const requestPayload = {
            file_id: fileId,
            config: requestData
        };
        
        // Ensure no file objects are included
        const requestBody = JSON.stringify(requestPayload);
        
        console.log('🔍 Final request body length:', requestBody.length);
        console.log('🔍 Final request body preview:', requestBody.substring(0, 200));
        
        console.log('🚀 About to make fetch request...');
        
        // Use XMLHttpRequest instead of fetch to avoid any potential interception
        const response = await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/translate');
            xhr.setRequestHeader('Content-Type', 'application/json');
            
            xhr.onload = () => {
                console.log('🚀 XMLHttpRequest completed:', xhr.status);
                resolve({
                    ok: xhr.status >= 200 && xhr.status < 300,
                    status: xhr.status,
                    json: () => Promise.resolve(JSON.parse(xhr.responseText))
                });
            };
            
            xhr.onerror = () => {
                console.error('🚀 XMLHttpRequest error');
                reject(new Error('Network error'));
            };
            
            console.log('🚀 Sending XMLHttpRequest with body:', requestBody.substring(0, 100));
            xhr.send(requestBody);
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

// Upload file and return file ID
async function uploadFile() {
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
    return result.file_id;
}

function collectTranslationSettings() {
    const settings = {
        service: serviceSelect.value,
        lang_from: langFromSelect.value,
        lang_to: langToSelect.value,
        page_range: pageRangeSelect.value,
        page_input: pageInput.value.trim() || null,
        threads: parseInt(document.getElementById('threads').value),
        no_mono: document.getElementById('noMono').checked,
        no_dual: document.getElementById('noDual').checked,
        dual_translate_first: document.getElementById('dualTranslateFirst').checked,
        use_alternating_pages_dual: document.getElementById('useAlternatingPagesDual').checked,
        watermark_output_mode: document.getElementById('watermarkMode').value,
        custom_system_prompt_input: document.getElementById('customSystemPrompt').value || null,
        min_text_length: parseInt(document.getElementById('minTextLength').value) || 10,
        rpc_doclayout: document.getElementById('rpcDoclayout').value.trim() || null,
        pool_max_workers: (() => {
            const value = parseInt(document.getElementById('poolMaxWorkers').value);
            return value > 0 ? value : null;
        })(),
        no_auto_extract_glossary: document.getElementById('noAutoExtractGlossary').checked,
        primary_font_family: document.getElementById('primaryFontFamily').value,
        skip_clean: document.getElementById('skipClean').checked,
        disable_rich_text_translate: document.getElementById('disableRichTextTranslate').checked,
        enhance_compatibility: document.getElementById('enhanceCompatibility').checked,
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
    progressText.textContent = status.stage || '处理中...';
    
    if (status.part_index && status.total_parts) {
        progressDetails.textContent = `第${status.part_index}/${status.total_parts}部分`;
        if (status.stage_current && status.stage_total) {
            progressDetails.textContent += ` - 第${status.stage_current}/${status.stage_total}步`;
        }
    }
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
    
    // Configure download buttons
    if (result.mono_pdf_path) {
        downloadMono.style.display = 'inline-block';
    }
    if (result.dual_pdf_path) {
        downloadDual.style.display = 'inline-block';
    }
    
    // Show stats
    translationStats.innerHTML = `
        <h4>翻译完成！</h4>
        <p><strong>处理时间：</strong> ${result.total_seconds.toFixed(2)} 秒</p>
        <p><strong>单语PDF：</strong> ${result.mono_pdf_path ? '可下载' : '未生成'}</p>
        <p><strong>双语PDF：</strong> ${result.dual_pdf_path ? '可下载' : '未生成'}</p>
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
    } catch (error) {
        console.error('Download error:', error);
        showError('下载失败，请重试。');
    }
}

function resetTranslationUI() {
    translateBtn.disabled = currentFile === null;
    translateBtn.textContent = '开始翻译';
    cancelBtn.style.display = 'none';
    progressSection.style.display = 'none';
    resultsSection.style.display = 'none';
    downloadMono.style.display = 'none';
    downloadDual.style.display = 'none';
    
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