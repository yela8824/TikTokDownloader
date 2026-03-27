const API_BASE = '';
const token = localStorage.getItem('api_token') || '';

function setToken(t) {
    localStorage.setItem('api_token', t);
    location.reload();
}

function api(endpoint, data = null, method = 'POST') {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (token) options.headers['token'] = token;
    if (data) options.body = JSON.stringify(data);
    return fetch(API_BASE + endpoint, options).then(r => {
        if (!r.ok) {
            return r.json().then(err => {
                throw err;
            });
        }
        return r.json();
    });
}

function showResult(data) {
    $('#result-output').text(JSON.stringify(data, null, 2));
}

const douyinFields = {
    detail: [{ name: 'detail_id', label: '作品ID', required: true }],
    account: [
        { name: 'sec_user_id', label: '账号sec_uid', required: true },
        { name: 'tab', label: '类型(post/like)', default: 'post' },
        { name: 'pages', label: '最大请求次数', type: 'number' },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ],
    mix: [
        { name: 'mix_id', label: '合集ID' },
        { name: 'detail_id', label: '作品ID' },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ],
    live: [
        { name: 'web_rid', label: '直播web_rid', required: true },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ],
    comment: [
        { name: 'detail_id', label: '作品ID', required: true },
        { name: 'pages', label: '最大请求次数', type: 'number' },
        { name: 'reply', label: '包含回复', type: 'checkbox' },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ],
    search: [
        { name: 'keyword', label: '关键词', required: true },
        { name: 'search_type', label: '搜索类型(general/video/user/live)', default: 'general' },
        { name: 'pages', label: '总页数', type: 'number' },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ]
};

const tiktokFields = {
    detail: [{ name: 'detail_id', label: '作品ID', required: true }],
    account: [
        { name: 'sec_user_id', label: '账号secUid', required: true },
        { name: 'tab', label: '类型(post/like)', default: 'post' },
        { name: 'pages', label: '最大请求次数', type: 'number' },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ],
    mix: [
        { name: 'mix_id', label: '合集ID', required: true },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ],
    live: [
        { name: 'room_id', label: '直播room_id', required: true },
        { name: 'cookie', label: 'Cookie' },
        { name: 'proxy', label: '代理' }
    ]
};

function renderFields(container, fields) {
    container.empty();
    fields.forEach(f => {
        const id = f.name;
        let html = '';
        if (f.type === 'checkbox') {
            html = `<div class="mb-3 form-check">
                <input type="checkbox" class="form-check-input" id="${id}" name="${id}">
                <label class="form-check-label" for="${id}">${f.label}</label>
            </div>`;
        } else {
            html = `<div class="mb-3">
                <label class="form-label" for="${id}">${f.label}${f.required ? ' *' : ''}</label>
                <input type="${f.type || 'text'}" class="form-control" id="${id}" name="${id}" ${f.required ? 'required' : ''} ${f.default ? 'value="' + f.default + '"' : ''}>
            </div>`;
        }
        container.append(html);
    });
}

function renderSettingsFields(settings) {
    const container = $('#settings-fields');
    container.empty();
    for (const [key, value] of Object.entries(settings)) {
        if (value === null || value === undefined) continue;
        const vtype = typeof value;
        if (vtype === 'object') {
            if (Array.isArray(value)) {
                container.append(`<div class="mb-3">
                    <label class="form-label">${key}</label>
                    <textarea class="form-control" name="${key}" rows="3">${JSON.stringify(value, null, 2)}</textarea>
                </div>`);
            } else {
                container.append(`<div class="mb-3">
                    <label class="form-label">${key}</label>
                    <textarea class="form-control" name="${key}" rows="3">${JSON.stringify(value, null, 2)}</textarea>
                </div>`);
            }
        } else if (vtype === 'boolean') {
            container.append(`<div class="mb-3 form-check">
                <input type="checkbox" class="form-check-input" id="${key}" name="${key}" ${value ? 'checked' : ''}>
                <label class="form-check-label" for="${key}">${key}</label>
            </div>`);
        } else {
            container.append(`<div class="mb-3">
                <label class="form-label">${key}</label>
                <input type="text" class="form-control" id="${key}" name="${key}" value="${value}">
            </div>`);
        }
    }
}

function getSettings() {
    api('/settings', null, 'GET').then(data => {
        renderSettingsFields(data);
        $('#system-status').html(`<span class="text-success"><i class="bi bi-check-circle"></i> 已连接</span>`);
    }).catch(err => {
        const msg = err.detail || err.message || '连接失败';
        $('#system-status').html(`<span class="text-danger"><i class="bi bi-x-circle"></i> ${msg}</span>`);
    });
}

function saveSettings() {
    const data = {};
    $('#settings-form').serializeArray().forEach(item => {
        let val = item.value;
        if (val.startsWith('{') || val.startsWith('[')) {
            try { val = JSON.parse(val); } catch(e) {}
        }
        data[item.name] = val;
    });
    $('#settings-form input[type="checkbox"]').each(function() {
        data[this.name] = this.checked;
    });
    api('/settings', data, 'POST').then(data => {
        alert('设置已保存');
        renderSettingsFields(data);
    }).catch(err => {
        alert('保存失败: ' + (err.detail || err.message || '未知错误'));
    });
}

function submitDouyin() {
    const type = $('#douyin-type-pills .nav-link.active').data('type');
    const formData = {};
    $('#douyin-form').serializeArray().forEach(item => {
        if (item.value) formData[item.name] = item.value;
    });
    const endpoint = '/douyin/' + type;
    api(endpoint, formData).then(showResult).catch(err => {
        showResult(err);
    });
}

function submitTiktok() {
    const type = $('#tiktok-type-pills .nav-link.active').data('type');
    const formData = {};
    $('#tiktok-form').serializeArray().forEach(item => {
        if (item.value) formData[item.name] = item.value;
    });
    const endpoint = '/tiktok/' + type;
    api(endpoint, formData).then(showResult).catch(err => {
        showResult(err);
    });
}

function loadRecords() {
    $('#records-table').html('<tr><td colspan="4" class="text-center text-muted">功能暂未实现</td></tr>');
}

$(function() {
    if (!token) {
        const t = prompt('请输入API Token:');
        if (t) setToken(t);
    }

    $('.nav-link[data-page]').click(function() {
        $('.nav-link[data-page]').removeClass('active');
        $(this).addClass('active');
        const page = $(this).data('page');
        $('[id^="page-"]').hide();
        $('#page-' + page).show();
        if (page === 'settings') getSettings();
        if (page === 'records') loadRecords();
    });

    $('button[data-page]').click(function() {
        const page = $(this).data('page');
        $('.nav-link[data-page]').removeClass('active');
        $('.nav-link[data-page="' + page + '"]').addClass('active');
        $('[id^="page-"]').hide();
        $('#page-' + page).show();
        if (page === 'settings') getSettings();
        if (page === 'records') loadRecords();
    });

    $('#douyin-type-pills .nav-link').click(function() {
        $('#douyin-type-pills .nav-link').removeClass('active');
        $(this).addClass('active');
        renderFields($('#douyin-fields'), douyinFields[$(this).data('type')]);
    });

    $('#tiktok-type-pills .nav-link').click(function() {
        $('#tiktok-type-pills .nav-link').removeClass('active');
        $(this).addClass('active');
        renderFields($('#tiktok-fields'), tiktokFields[$(this).data('type')]);
    });

    $('.nav-tabs .nav-link').click(function() {
        $('.nav-tabs .nav-link').removeClass('active');
        $(this).addClass('active');
        const tab = $(this).data('tab');
        $('#tab-douyin, #tab-tiktok').hide();
        $('#tab-' + tab).show();
    });

    $('#douyin-form').submit(function(e) { e.preventDefault(); submitDouyin(); });
    $('#tiktok-form').submit(function(e) { e.preventDefault(); submitTiktok(); });
    $('#settings-form').submit(function(e) { e.preventDefault(); saveSettings(); });

    renderFields($('#douyin-fields'), douyinFields.detail);
    renderFields($('#tiktok-fields'), tiktokFields.detail);
    getSettings();
});