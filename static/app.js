$(document).ready(function() {
    let selectedFiles = [];
    let currentDocumentId = null;

    // Upload area drag and drop
    const uploadArea = $('#uploadArea');
    const fileInput = $('#fileInput');
    const fileList = $('#fileList');
    const uploadBtn = $('#uploadBtn');

    // Click to select files
    uploadArea.on('click', function() {
        fileInput.click();
    });

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.on(eventName, function(e) {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    // Highlight drop area when item is dragged over
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.on(eventName, function() {
            uploadArea.addClass('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.on(eventName, function() {
            uploadArea.removeClass('drag-over');
        });
    });

    // Handle dropped files
    uploadArea.on('drop', function(e) {
        const files = e.originalEvent.dataTransfer.files;
        handleFiles(files);
    });

    // Handle selected files
    fileInput.on('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        selectedFiles = Array.from(files);
        displayFileList();
        uploadBtn.prop('disabled', selectedFiles.length === 0);
    }

    function displayFileList() {
        if (selectedFiles.length === 0) {
            fileList.hide();
            return;
        }

        fileList.show();
        fileList.html('<h3 style="color: #667eea; margin-bottom: 10px;">已選擇的檔案:</h3>');

        selectedFiles.forEach((file, index) => {
            const fileItem = $('<div class="file-item"></div>');
            fileItem.html(`
                <span class="file-name">${file.name} (${formatFileSize(file.size)})</span>
                <button class="remove-btn" data-index="${index}">移除</button>
            `);
            fileList.append(fileItem);
        });

        // Handle remove button
        $('.remove-btn').on('click', function(e) {
            e.stopPropagation();
            const index = $(this).data('index');
            selectedFiles.splice(index, 1);
            displayFileList();
            uploadBtn.prop('disabled', selectedFiles.length === 0);
        });
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    // Upload files
    uploadBtn.on('click', function() {
        if (selectedFiles.length === 0) return;

        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append('files[]', file);
        });

        $('#uploadLoading').show();
        $('#uploadStatus').hide();

        $.ajax({
            url: '/api/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                $('#uploadLoading').hide();

                // Count results
                const uploadedCount = response.uploaded.length;
                const skippedCount = response.skipped ? response.skipped.length : 0;
                const errorCount = response.errors.length;

                // Build message HTML
                let messageHtml = '';
                let icon = 'success';
                let title = '上傳完成';

                if (uploadedCount > 0) {
                    messageHtml += `<p style="color: #155724; font-size: 16px;">✅ 成功上傳 ${uploadedCount} 個檔案</p>`;
                }

                if (skippedCount > 0) {
                    messageHtml += `<p style="color: #856404; font-size: 16px; margin-top: 10px;">⚠️ ${skippedCount} 個檔案因重複而跳過</p>`;
                    messageHtml += '<div style="text-align: left; margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 5px;">';
                    response.skipped.forEach(skip => {
                        const uploadDate = new Date(skip.existing_upload_date).toLocaleString('zh-TW');
                        messageHtml += `<p style="margin: 5px 0; font-size: 14px;">📄 ${skip.filename}<br><small style="color: #666;">已存在：${skip.existing_filename} (${uploadDate})</small></p>`;
                    });
                    messageHtml += '</div>';
                    if (uploadedCount === 0) {
                        icon = 'warning';
                        title = '檔案重複';
                    }
                }

                if (errorCount > 0) {
                    messageHtml += `<p style="color: #721c24; font-size: 16px; margin-top: 10px;">❌ ${errorCount} 個檔案上傳失敗</p>`;
                    if (uploadedCount === 0 && skippedCount === 0) {
                        icon = 'error';
                        title = '上傳失敗';
                    }
                }

                Swal.fire({
                    title: title,
                    html: messageHtml,
                    icon: icon,
                    confirmButtonColor: '#667eea',
                    timer: skippedCount > 0 ? undefined : 3000
                });

                // Reset
                selectedFiles = [];
                fileInput.val('');
                displayFileList();
                uploadBtn.prop('disabled', true);

                // Refresh search results if search was performed
                if ($('#resultsContainer').is(':visible')) {
                    performSearch($('#searchInput').val());
                }
            },
            error: function(xhr) {
                $('#uploadLoading').hide();
                Swal.fire({
                    title: '上傳失敗',
                    text: xhr.responseJSON?.error || '未知錯誤',
                    icon: 'error',
                    confirmButtonColor: '#667eea'
                });
            }
        });
    });

    function showStatus(type, message) {
        const statusDiv = $('#uploadStatus');
        statusDiv.removeClass('status-success status-error status-warning');
        statusDiv.addClass('status-' + type);
        statusDiv.text(message);
        statusDiv.show();

        setTimeout(() => {
            statusDiv.fadeOut();
        }, 8000);
    }

    // Search functionality
    const searchInput = $('#searchInput');
    const searchBtn = $('#searchBtn');
    const resultsContainer = $('#resultsContainer');
    const searchResults = $('#searchResults');

    // Search on button click
    searchBtn.on('click', function() {
        performSearch(searchInput.val().trim());
    });

    // Search on Enter key
    searchInput.on('keypress', function(e) {
        if (e.which === 13) {
            performSearch(searchInput.val().trim());
        }
    });

    function performSearch(query) {
        $('#searchLoading').show();
        resultsContainer.hide();

        $.ajax({
            url: '/api/search',
            type: 'GET',
            data: { q: query },
            success: function(response) {
                $('#searchLoading').hide();
                displaySearchResults(response.results, query);
            },
            error: function(xhr) {
                $('#searchLoading').hide();
                Swal.fire({
                    title: '搜尋失敗',
                    text: xhr.responseJSON?.error || '未知錯誤',
                    icon: 'error',
                    confirmButtonColor: '#667eea'
                });
            }
        });
    }

    function displaySearchResults(results, query) {
        resultsContainer.show();
        $('#resultCount').text(results.length);

        if (results.length === 0) {
            searchResults.html('<p style="color: #999; text-align: center; padding: 40px;">沒有找到相關文件</p>');
            return;
        }

        searchResults.empty();

        results.forEach(result => {
            const resultItem = $('<div class="result-item"></div>');

            const fileName = result.original_filename;
            const fileType = result.file_type.toUpperCase();
            const uploadDate = new Date(result.upload_date).toLocaleString('zh-TW');
            let preview = result.preview || '(無內容預覽)';

            // Highlight search term in preview
            if (query && result.preview) {
                const regex = new RegExp('(' + escapeRegExp(query) + ')', 'gi');
                preview = preview.replace(regex, '<mark style="background: #ffeb3b;">$1</mark>');
            }

            resultItem.html(`
                <div class="result-item-header">
                    <div class="result-item-content">
                        <h3>${fileName}</h3>
                        <div class="meta">類型: ${fileType} | 上傳日期: ${uploadDate}</div>
                        <div class="preview">${preview}...</div>
                    </div>
                    <div class="result-actions">
                        <button class="delete-btn" data-id="${result.id}" data-name="${fileName}">🗑️ 刪除</button>
                    </div>
                </div>
            `);

            // Click on content to view document
            resultItem.find('.result-item-content').on('click', function(e) {
                e.stopPropagation();
                showDocument(result.id);
            });

            // Delete button handler
            resultItem.find('.delete-btn').on('click', function(e) {
                e.stopPropagation();
                const docId = $(this).data('id');
                const docName = $(this).data('name');
                confirmDelete(docId, docName);
            });

            searchResults.append(resultItem);
        });
    }

    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // Delete functionality
    function confirmDelete(docId, docName) {
        Swal.fire({
            title: '確定要刪除嗎？',
            html: `您即將刪除文件：<br><strong>${docName}</strong><br><br>此操作無法復原！`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ff4444',
            cancelButtonColor: '#667eea',
            confirmButtonText: '是的，刪除！',
            cancelButtonText: '取消',
            reverseButtons: true
        }).then((result) => {
            if (result.isConfirmed) {
                deleteDocument(docId);
            }
        });
    }

    function deleteDocument(docId) {
        // Show loading
        Swal.fire({
            title: '刪除中...',
            text: '請稍候',
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        $.ajax({
            url: `/api/delete/${docId}`,
            type: 'DELETE',
            success: function(response) {
                Swal.fire({
                    title: '刪除成功！',
                    text: '文件已成功刪除',
                    icon: 'success',
                    confirmButtonColor: '#667eea',
                    timer: 2000
                });

                // Refresh search results
                performSearch($('#searchInput').val());
            },
            error: function(xhr) {
                Swal.fire({
                    title: '刪除失敗',
                    text: xhr.responseJSON?.error || '發生未知錯誤',
                    icon: 'error',
                    confirmButtonColor: '#667eea'
                });
            }
        });
    }

    // Document modal
    const documentModal = $('#documentModal');
    const closeModal = $('#closeModal');
    const downloadBtn = $('#downloadBtn');

    function showDocument(docId) {
        currentDocumentId = docId;

        $.ajax({
            url: `/api/document/${docId}`,
            type: 'GET',
            success: function(doc) {
                $('#modalTitle').text(doc.original_filename);
                $('#modalMeta').text(
                    `類型: ${doc.file_type.toUpperCase()} | ` +
                    `上傳日期: ${new Date(doc.upload_date).toLocaleString('zh-TW')}`
                );
                $('#modalContent').text(doc.content || '(此文件沒有可顯示的內容)');
                documentModal.fadeIn();
            },
            error: function() {
                Swal.fire({
                    title: '載入失敗',
                    text: '無法載入文件內容',
                    icon: 'error',
                    confirmButtonColor: '#667eea'
                });
            }
        });
    }

    closeModal.on('click', function() {
        documentModal.fadeOut();
        currentDocumentId = null;
    });

    // Close modal when clicking outside
    documentModal.on('click', function(e) {
        if (e.target === this) {
            documentModal.fadeOut();
            currentDocumentId = null;
        }
    });

    // Download functionality
    downloadBtn.on('click', function() {
        if (currentDocumentId) {
            window.location.href = `/api/download/${currentDocumentId}`;
        }
    });

    // Modal delete functionality
    $('#modalDeleteBtn').on('click', function() {
        if (currentDocumentId) {
            const docName = $('#modalTitle').text();
            documentModal.fadeOut();
            confirmDelete(currentDocumentId, docName);
        }
    });

    // Close modal with Escape key
    $(document).on('keydown', function(e) {
        if (e.key === 'Escape' && documentModal.is(':visible')) {
            documentModal.fadeOut();
            currentDocumentId = null;
        }
    });

    // Load all documents on page load
    performSearch('');
});
