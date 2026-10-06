import re

toast_script = """
function showCustomAlert(message, type = 'danger') {
    const toastContainerId = 'customToastContainer';
    let container = document.getElementById(toastContainerId);
    if (!container) {
        container = document.createElement('div');
        container.id = toastContainerId;
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    const toastId = 'toast-' + Math.random().toString(36).substr(2, 9);
    const bgClass = type === 'danger' ? 'bg-danger text-white' : 'bg-success text-white';
    const iconClass = type === 'danger' ? 'fas fa-exclamation-circle' : 'fas fa-check-circle';
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center border-0 ${bgClass}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body d-flex align-items-center gap-2 fs-9">
                    <i class="${iconClass} fs-8"></i>
                    <span>${message}</span>
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = document.getElementById(toastId);
    if (window.bootstrap && window.bootstrap.Toast) {
        const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
        });
    } else {
        alert(message);
    }
}
"""

new_widget_input_area = """
<!-- Chat Input Form -->
<div class="p-3 bg-white border-top border-300 position-relative {% if not start_active %}d-none{% endif %}" id="chat-input-area">
    <!-- Quick Action Bar -->
    <div class="d-flex align-items-center justify-content-between mb-2">
        <div class="d-flex align-items-center gap-2 overflow-auto" style="white-space: nowrap; padding-bottom: 4px;">
            <button type="button" class="btn btn-xs btn-primary rounded-pill px-3 py-1 fs-10 shadow-sm" onclick="openCoreQuickRepliesModal()" title="View all Quick Reply Templates, Keywords & Media">
                <i class="fas fa-bolt text-warning me-1"></i> Quick Replies
            </button>
            <button type="button" class="btn btn-xs btn-outline-success rounded-pill px-3 py-1 fs-10 shadow-sm" onclick="insertCoreSellerTemplate()" title="Load Seller Onboarding Template">
                <i class="fas fa-store me-1"></i> Seller Template <kbd class="ms-1 bg-success-subtle text-success border-0 px-1">/seller</kbd>
            </button>
            <button type="button" class="btn btn-xs btn-outline-danger rounded-pill px-3 py-1 fs-10 shadow-sm" id="coreBtnTogglePdf" onclick="toggleCorePdfAttachment()">
                <i class="fas fa-file-pdf me-1"></i> <span id="corePdfToggleText">Attach PDF Guide</span>
            </button>
        </div>
        
        <div class="d-flex align-items-center gap-2">
            <a href="{% url 'whatsapp_quick_replies' %}" target="_blank" class="btn btn-xs btn-link text-decoration-none px-2 py-1 fs-10" title="Manage Templates, Keywords & Attachments">
                <i class="fas fa-cog me-1"></i>Manage
            </a>
            <a href="#" id="coreWaWebSendDirectBtn" target="_blank" class="btn btn-xs btn-success rounded-pill px-3 py-1 fs-10 shadow-sm" title="Open in WhatsApp Web">
                <i class="fab fa-whatsapp me-1"></i> WA Web
            </a>
        </div>
    </div>

    <!-- Attached Seller Guide PDF Chip -->
    <div id="coreAttachedPdfChip" class="d-none alert alert-primary py-1 px-3 mb-2 fs-10 d-flex align-items-center border-0 rounded-pill shadow-sm w-fit-content">
        <i class="fas fa-file-pdf text-danger fs-8 me-2"></i>
        <div class="me-3">
            <strong>Seller_Onboarding_Guide.pdf</strong>
            <span class="badge bg-primary text-white ms-1">Auto-Attached</span>
        </div>
        <button type="button" class="btn-close fs-11" onclick="toggleCorePdfAttachment(false)"></button>
    </div>

    <!-- Custom File Attachment Tray -->
    <div id="coreCustomAttachmentTray" class="d-none alert alert-secondary py-2 px-3 mb-2 fs-10 d-flex align-items-center gap-3 border shadow-sm rounded-3">
        <div id="coreCustomAttachmentPreview" class="d-flex align-items-center justify-content-center bg-white rounded border overflow-hidden" style="width: 48px; height: 48px; min-width: 48px;">
            <!-- Dynamic Image thumbnail or Document icon -->
        </div>
        <div class="flex-grow-1 min-w-0">
            <div class="fw-bold text-body-emphasis text-truncate" id="coreCustomAttachmentName">filename.pdf</div>
            <div class="text-body-tertiary fs-11 d-flex align-items-center gap-2 flex-wrap">
                <span id="coreCustomAttachmentSize">0 KB</span>
                <span class="badge badge-phoenix badge-phoenix-primary fs-11" id="coreCustomAttachmentTypeBadge">Document</span>
                <span class="text-success"><i class="fas fa-check-circle me-1"></i>Ready to send</span>
            </div>
        </div>
        <button type="button" class="btn btn-sm btn-phoenix-danger p-1 rounded-circle ms-auto" onclick="removeCoreCustomAttachment()" title="Remove attachment">
            <i class="fas fa-times"></i>
        </button>
    </div>

    <!-- Keyword Dropdown Suggestions Box -->
    <div id="coreKeywordSuggestionsBox" class="dropdown-menu shadow-lg p-0 fs-10 border border-primary-subtle position-absolute d-none" style="bottom: 100%; left: 15px; z-index: 1050; min-width: 360px; max-width: 460px; max-height: 280px; overflow-y: auto; margin-bottom: 8px;">
        <div class="px-3 py-2 text-muted fw-bold border-bottom fs-11 text-uppercase d-flex align-items-center justify-content-between sticky-top bg-body">
            <span><i class="fas fa-bolt text-warning me-1"></i> Matching Quick Replies</span>
            <span class="badge bg-light text-secondary">↑↓ Navigate • Enter to Insert</span>
        </div>
        <div id="coreKeywordSuggestionsItems">
            <!-- Injected dynamically -->
        </div>
    </div>

    <form id="chat-form" class="w-100 m-0">
        <input type="hidden" id="active-customer-id" value="{{ initial_customer_id|default:'' }}">
        <input type="hidden" id="coreAttachSellerGuideInput" value="false">
        <input type="hidden" id="coreQuickReplyMediaIds" name="quick_reply_media_ids" value="">
        <input type="hidden" id="coreQuickReplyMetaTemplates" name="quick_reply_meta_templates" value="">
        <input type="file" id="coreAttachmentFileInput" class="d-none" accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,video/*" onchange="handleCoreFileInputChange(this.files)">

        <div class="input-group shadow-sm bg-white rounded-3 border border-300 focus-ring-primary transition-base" style="border-radius: 20px !important; overflow: hidden;">
            <!-- Left Actions -->
            <button type="button" class="btn btn-link text-decoration-none px-3 border-end border-200 bg-light-hover" data-bs-toggle="dropdown" aria-expanded="false" title="Insert Emoji">
                <i class="fas fa-smile fs-8 text-secondary"></i>
            </button>
            <div class="dropdown-menu p-2 shadow-lg border-0" style="min-width: 200px;">
                <div class="d-flex flex-wrap gap-1 justify-content-center">
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('👍')">👍</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('🙏')">🙏</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('✅')">✅</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('📦')">📦</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('🤝')">🤝</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('📞')">📞</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('📄')">📄</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('😀')">😀</button>
                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertCoreEmoji('🚀')">🚀</button>
                </div>
            </div>

            <button type="button" class="btn btn-link text-decoration-none px-3 border-end border-200 bg-light-hover" id="coreAttachTriggerBtn" onclick="document.getElementById('coreAttachmentFileInput').click()" title="Attach File">
                <i class="fas fa-paperclip fs-8 text-primary"></i>
            </button>

            <!-- Text Area -->
            <textarea id="chat-input" class="form-control border-0 fs-9 py-3 shadow-none" rows="1" placeholder="Type a message, /keyword (e.g. /seller), or paste..." autocomplete="off" style="resize: none; min-height: 48px; max-height: 150px; overflow-y: auto;" oninput="this.style.height = '';this.style.height = this.scrollHeight + 'px'"></textarea>

            <!-- Right Actions -->
            <button type="button" class="btn btn-link text-decoration-none px-3 border-start border-200 bg-light-hover" onclick="openMetaTemplateModal()" title="Send WhatsApp Meta Template">
                <i class="fab fa-whatsapp fs-8 text-success"></i>
            </button>

            <button type="submit" class="btn btn-primary px-4 fw-bold" id="coreSendMsgBtn" style="border-radius: 0 20px 20px 0;">
                <i class="fas fa-paper-plane me-1"></i> <span id="coreSendMsgBtnText">Send</span>
            </button>
        </div>
        <div class="d-flex align-items-center justify-content-between mt-2 text-muted fs-11 px-2">
            <span>Tip: Type <kbd class="bg-body-secondary text-body">/</kbd> for Quick Replies. <kbd class="bg-body-secondary text-body">Ctrl+V</kbd> to paste image. Press <kbd class="bg-body-secondary text-body">Ctrl+Enter</kbd> to send.</span>
        </div>
    </form>
</div>
"""

new_inbox_input_area = """
                <!-- Input Footer -->
                <div class="p-3 bg-white border-top border-300 position-relative">
                    <!-- Quick Action Bar -->
                    <div class="d-flex align-items-center justify-content-between mb-2">
                        <div class="d-flex align-items-center gap-2 overflow-auto" style="white-space: nowrap; padding-bottom: 4px;">
                            <button type="button" class="btn btn-xs btn-primary rounded-pill px-3 py-1 fs-10 shadow-sm" onclick="openEmployeeQuickRepliesModal()" title="View all Quick Reply Templates, Keywords & Media">
                                <i class="fas fa-bolt text-warning me-1"></i> Quick Replies
                            </button>
                            <button type="button" class="btn btn-xs btn-outline-success rounded-pill px-3 py-1 fs-10 shadow-sm" onclick="insertSellerTemplate()" title="Load Seller Onboarding Template">
                                <i class="fas fa-store me-1"></i> Seller Template <kbd class="ms-1 bg-success-subtle text-success border-0 px-1">/seller</kbd>
                            </button>
                            <button type="button" class="btn btn-xs btn-outline-danger rounded-pill px-3 py-1 fs-10 shadow-sm" id="btnTogglePdf" onclick="togglePdfAttachment()">
                                <i class="fas fa-file-pdf me-1"></i> <span id="pdfToggleText">Attach PDF Guide</span>
                            </button>
                        </div>
                        
                        <div class="d-flex align-items-center gap-2">
                            <a href="{% url 'whatsapp_quick_replies' %}" target="_blank" class="btn btn-xs btn-link text-decoration-none px-2 py-1 fs-10" title="Manage Templates, Keywords & Attachments">
                                <i class="fas fa-cog me-1"></i>Manage
                            </a>
                            <a href="#" id="waWebSendDirectBtn" target="_blank" class="btn btn-xs btn-success rounded-pill px-3 py-1 fs-10 shadow-sm" title="Open in WhatsApp Web">
                                <i class="fab fa-whatsapp me-1"></i> WA Web
                            </a>
                        </div>
                    </div>

                    <!-- Attached Seller Guide PDF Chip -->
                    <div id="attachedPdfChip" class="d-none alert alert-primary py-1 px-3 mb-2 fs-10 d-flex align-items-center border-0 rounded-pill shadow-sm w-fit-content">
                        <i class="fas fa-file-pdf text-danger fs-8 me-2"></i>
                        <div class="me-3">
                            <strong>Seller_Onboarding_Guide.pdf</strong>
                            <span class="badge bg-primary text-white ms-1">Auto-Attached</span>
                        </div>
                        <button type="button" class="btn-close fs-11" onclick="togglePdfAttachment(false)"></button>
                    </div>

                    <!-- Custom File Attachment Tray -->
                    <div id="employeeCustomAttachmentTray" class="d-none alert alert-secondary py-2 px-3 mb-2 fs-10 d-flex align-items-center gap-3 border shadow-sm rounded-3">
                        <div id="employeeCustomAttachmentPreview" class="d-flex align-items-center justify-content-center bg-white rounded border overflow-hidden" style="width: 48px; height: 48px; min-width: 48px;">
                            <!-- Dynamic Image thumbnail or Document icon -->
                        </div>
                        <div class="flex-grow-1 min-w-0">
                            <div class="fw-bold text-body-emphasis text-truncate" id="employeeCustomAttachmentName">filename.pdf</div>
                            <div class="text-body-tertiary fs-11 d-flex align-items-center gap-2 flex-wrap">
                                <span id="employeeCustomAttachmentSize">0 KB</span>
                                <span class="badge badge-phoenix badge-phoenix-primary fs-11" id="employeeCustomAttachmentTypeBadge">Document</span>
                                <span class="text-success"><i class="fas fa-check-circle me-1"></i>Ready to send</span>
                            </div>
                        </div>
                        <button type="button" class="btn btn-sm btn-phoenix-danger p-1 rounded-circle ms-auto" onclick="removeEmployeeCustomAttachment()" title="Remove attachment">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <!-- Keyword Dropdown Suggestions Box -->
                    <div id="keywordSuggestionsBox" class="dropdown-menu shadow-lg p-0 fs-10 border border-primary-subtle position-absolute d-none" style="bottom: 100%; left: 15px; z-index: 1050; min-width: 360px; max-width: 460px; max-height: 280px; overflow-y: auto; margin-bottom: 8px;">
                        <div class="px-3 py-2 text-muted fw-bold border-bottom fs-11 text-uppercase d-flex align-items-center justify-content-between sticky-top bg-body">
                            <span><i class="fas fa-bolt text-warning me-1"></i> Matching Quick Replies</span>
                            <span class="badge bg-light text-secondary">↑↓ Navigate • Enter to Insert</span>
                        </div>
                        <div id="keywordSuggestionsItems">
                            <!-- Injected dynamically -->
                        </div>
                    </div>

                    <form id="sendMessageForm" class="w-100 m-0" onsubmit="submitMessage(event)">
                        {% csrf_token %}
                        <input type="hidden" name="attach_seller_guide" id="attachSellerGuideInput" value="false">
                        <input type="hidden" name="quick_reply_media_ids" id="employeeQuickReplyMediaIds" value="">
                        <input type="hidden" name="quick_reply_meta_templates" id="employeeQuickReplyMetaTemplates" value="">
                        <input type="file" id="employeeAttachmentFileInput" class="d-none" accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,video/*" onchange="handleEmployeeFileInputChange(this.files)">

                        <div class="input-group shadow-sm bg-white rounded-3 border border-300 focus-ring-primary transition-base" style="border-radius: 20px !important; overflow: hidden;">
                            <!-- Left Actions -->
                            <button type="button" class="btn btn-link text-decoration-none px-3 border-end border-200 bg-light-hover" data-bs-toggle="dropdown" aria-expanded="false" title="Insert Emoji">
                                <i class="fas fa-smile fs-8 text-secondary"></i>
                            </button>
                            <div class="dropdown-menu p-2 shadow-lg border-0" style="min-width: 200px;">
                                <div class="d-flex flex-wrap gap-1 justify-content-center">
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('👍')">👍</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('🙏')">🙏</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('✅')">✅</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('📦')">📦</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('🤝')">🤝</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('📞')">📞</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('📄')">📄</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('😀')">😀</button>
                                    <button type="button" class="btn btn-link p-1 text-decoration-none fs-7 lh-1 bg-light-hover rounded" onclick="insertEmployeeEmoji('🚀')">🚀</button>
                                </div>
                            </div>

                            <button type="button" class="btn btn-link text-decoration-none px-3 border-end border-200 bg-light-hover" id="employeeAttachTriggerBtn" onclick="document.getElementById('employeeAttachmentFileInput').click()" title="Attach File">
                                <i class="fas fa-paperclip fs-8 text-primary"></i>
                            </button>

                            <!-- Text Area -->
                            <textarea name="message" id="messageInput" class="form-control border-0 fs-9 py-3 shadow-none" rows="1" placeholder="Type a message, /keyword (e.g. /seller), or paste..." autocomplete="off" style="resize: none; min-height: 48px; max-height: 150px; overflow-y: auto;" oninput="this.style.height = '';this.style.height = this.scrollHeight + 'px'"></textarea>

                            <!-- Right Actions -->
                            <button type="button" class="btn btn-link text-decoration-none px-3 border-start border-200 bg-light-hover" onclick="openMetaTemplateModal()" title="Send WhatsApp Meta Template">
                                <i class="fab fa-whatsapp fs-8 text-success"></i>
                            </button>

                            <button type="submit" class="btn btn-primary px-4 fw-bold" id="sendMsgBtn" style="border-radius: 0 20px 20px 0;">
                                <i class="fas fa-paper-plane me-1"></i> <span id="sendMsgBtnText">Send</span>
                            </button>
                        </div>
                        <div class="d-flex align-items-center justify-content-between mt-2 text-muted fs-11 px-2">
                            <span>Tip: Type <kbd class="bg-body-secondary text-body">/</kbd> for Quick Replies. <kbd class="bg-body-secondary text-body">Ctrl+V</kbd> to paste image. Press <kbd class="bg-body-secondary text-body">Ctrl+Enter</kbd> to send.</span>
                        </div>
                    </form>
                </div>
"""

def modify_file(filepath, replacement_fn):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    content = replacement_fn(content)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def fix_chat_widget(content):
    content = re.sub(r'<!-- Chat Input Form -->.*?</div>\s*<!-- Lightbox Modal for Image Previews -->', new_widget_input_area + '\n\n<!-- Lightbox Modal for Image Previews -->', content, flags=re.DOTALL)
    content = re.sub(r'alert\((.*?)\);', r'showCustomAlert(\1);', content)
    content = content.replace('let activeSuggestionIndex', toast_script + '\nlet activeSuggestionIndex')
    return content

def fix_whatsapp_inbox(content):
    content = re.sub(r'<!-- Input Footer -->.*?</div>\s*</div>\s*</div>\s*</div>', new_inbox_input_area + '\n            </div>\n        </div>\n    </div>\n</div>', content, flags=re.DOTALL)
    content = re.sub(r'alert\((.*?)\);', r'showCustomAlert(\1);', content)
    content = content.replace('let activeSuggestionIndex', toast_script + '\nlet activeSuggestionIndex')
    return content

modify_file('templates/core/partials/whatsapp_chat_widget.html', fix_chat_widget)
modify_file('templates/employee_portal/whatsapp_inbox.html', fix_whatsapp_inbox)

print("Modifications done safely with Python")
