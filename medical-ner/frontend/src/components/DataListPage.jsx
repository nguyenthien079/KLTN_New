import React, { useEffect, useMemo, useRef, useState } from 'react';
import { assignArticlesBulk, getLabelingArticle, getLabelingArticles, getUsers } from '../services/api';
import './DataListPage.css';

function normalizeKey(value) {
  return (value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function stemFromPath(pathOrName) {
  const name = (pathOrName || '').split(/[\\/]/).pop() || '';
  return name.replace(/\.(txt|pipe)$/i, '');
}

function parsePipeContent(pipeText) {
  return pipeText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split('||');
      if (parts.length < 4) return null;
      const startOffset = Number.parseInt(parts[2], 10);
      const endOffset = Number.parseInt(parts[3], 10);
      if (!Number.isFinite(startOffset) || !Number.isFinite(endOffset)) return null;
      return {
        entity_type: parts[1],
        start_offset: startOffset,
        end_offset: endOffset,
        surface_text: null,
        comment: null,
      };
    })
    .filter(Boolean);
}

function enrichAnnotationsWithSurfaceText(annotations, txtContent) {
  return annotations.map((ann) => ({
    ...ann,
    surface_text:
      ann.start_offset >= 0 && ann.end_offset <= txtContent.length
        ? txtContent.substring(ann.start_offset, ann.end_offset)
        : '',
  }));
}

export default function DataListPage() {
  const [serverItems, setServerItems] = useState([]);
  const [items, setItems] = useState([]);
  const [experts, setExperts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedArticleIds, setSelectedArticleIds] = useState([]);
  const [selectedExpertIds, setSelectedExpertIds] = useState([]);
  const [quickFrom, setQuickFrom] = useState('');
  const [quickTo, setQuickTo] = useState('');
  const [detail, setDetail] = useState(null);
  const [assigning, setAssigning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importedFolderName, setImportedFolderName] = useState('');
  const [importedAnnotationsByArticleId, setImportedAnnotationsByArticleId] = useState({});
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const folderInputRef = useRef(null);

  useEffect(() => {
    Promise.all([getLabelingArticles(), getUsers()])
      .then(([articleData, userData]) => {
        const rows = articleData || [];
        setServerItems(rows);
        setItems(rows);
        if (articleData?.length) setSelectedId(articleData[0].article_id);
        setExperts(
          (userData || []).filter((u) => {
            const roles = Array.isArray(u.roles)
              ? u.roles
              : String(u.role || '').split(',').map((r) => r.trim()).filter(Boolean);
            return roles.includes('chuyen_gia') && u.is_active !== false;
          })
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const openImportPicker = () => {
    folderInputRef.current?.click();
  };

  const handleImportFolder = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (files.length === 0) return;

    const txtFiles = files.filter((file) => file.name.toLowerCase().endsWith('.txt'));
    const pipeFiles = files.filter((file) => file.name.toLowerCase().endsWith('.pipe'));

    if (txtFiles.length === 0) {
      setErr('Folder đã chọn không có file .txt nào.');
      setMsg(null);
      return;
    }

    setImporting(true);
    setErr(null);
    setMsg(null);

    try {
      const pipeByKey = new Map();
      for (const pipeFile of pipeFiles) {
        const relativePath = pipeFile.webkitRelativePath || pipeFile.name;
        const key = normalizeKey(stemFromPath(relativePath));
        pipeByKey.set(key, parsePipeContent(await pipeFile.text()));
      }

      const importedRows = [];
      const importedAnnotations = {};
      const unmatched = [];

      for (const txtFile of txtFiles) {
        const relativePath = txtFile.webkitRelativePath || txtFile.name;
        const titleStem = stemFromPath(relativePath);
        const key = normalizeKey(titleStem);
        const txtContent = await txtFile.text();
        let annotations = pipeByKey.get(key) || [];
        annotations = enrichAnnotationsWithSurfaceText(annotations, txtContent);

        const matched = serverItems.find((item) => {
          const titleKey = normalizeKey(stemFromPath(item.title || ''));
          const urlKey = normalizeKey(stemFromPath(item.url || ''));
          return titleKey === key || urlKey === key;
        });

        if (!matched) {
          unmatched.push(txtFile.name);
          continue;
        }

        importedRows.push({
          ...matched,
          clean_text: txtContent,
          import_file_name: txtFile.name,
          import_annotations_count: annotations.length,
          import_folder_name: relativePath.split(/[\\/]/)[0] || '',
        });

        if (annotations.length > 0) {
          importedAnnotations[matched.article_id] = annotations;
        }
      }

      if (importedRows.length === 0) {
        setErr('Không khớp được file nào với dữ liệu hiện có trong hệ thống.');
        setItems(serverItems);
        setImportedFolderName('');
        setImportedAnnotationsByArticleId({});
        return;
      }

      setItems(importedRows);
      setImportedFolderName(importedRows[0].import_folder_name || '');
      setImportedAnnotationsByArticleId(importedAnnotations);
      setSelectedArticleIds([]);
      setSelectedId(importedRows[0].article_id);
      setMsg(
        unmatched.length > 0
          ? `Đã nhập ${importedRows.length} file khớp. Bỏ qua ${unmatched.length} file không khớp.`
          : `Đã nhập ${importedRows.length} file.`
      );
    } catch (error) {
      setErr(error?.message || 'Không thể đọc folder đã chọn.');
    } finally {
      setImporting(false);
    }
  };

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    getLabelingArticle(selectedId).then(setDetail).catch(() => setDetail(null));
  }, [selectedId]);

  const selectedTitle = useMemo(() => {
    const current = items.find((x) => x.article_id === selectedId);
    return current?.title || current?.url || '—';
  }, [items, selectedId]);

  const applyQuickSelect = () => {
    const from = Number.parseInt(quickFrom, 10);
    const to = Number.parseInt(quickTo, 10);

    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 1 || to < 1) {
      setErr('Vui lòng nhập 2 số STT hợp lệ lớn hơn 0.');
      setMsg(null);
      return;
    }

    const start = Math.min(from, to);
    const end = Math.max(from, to);
    const selectedIds = items
      .slice(start - 1, end)
      .map((item) => item.article_id);

    if (selectedIds.length === 0) {
      setErr('Khoảng STT không có file nào để chọn.');
      setMsg(null);
      return;
    }

    setSelectedArticleIds((prev) => Array.from(new Set([...prev, ...selectedIds])));
    setErr(null);
    setMsg(`Đã chọn nhanh ${selectedIds.length} file/text từ STT ${start} đến ${end}.`);
  };

  const toggleArticle = (articleId) => {
    setSelectedArticleIds((prev) =>
      prev.includes(articleId) ? prev.filter((id) => id !== articleId) : [...prev, articleId]
    );
  };

  const toggleExpert = (expertId) => {
    setSelectedExpertIds((prev) =>
      prev.includes(expertId) ? prev.filter((id) => id !== expertId) : [...prev, expertId]
    );
  };

  const handleAssign = async () => {
    if (selectedArticleIds.length === 0) {
      setErr('Vui lòng chọn ít nhất một file/text để bàn giao.');
      setMsg(null);
      return;
    }
    if (selectedExpertIds.length === 0) {
      setErr('Vui lòng chọn ít nhất một chuyên gia.');
      setMsg(null);
      return;
    }

    setAssigning(true);
    setErr(null);
    setMsg(null);
    try {
      const initialAnnotations = {};
      selectedArticleIds.forEach((articleId) => {
        if (importedAnnotationsByArticleId[articleId]?.length) {
          initialAnnotations[String(articleId)] = importedAnnotationsByArticleId[articleId];
        }
      });

      const result = await assignArticlesBulk(selectedArticleIds, selectedExpertIds, false, initialAnnotations);
      setMsg(`Đã bàn giao thành công. Tạo mới: ${result.created}, bỏ qua (đã tồn tại): ${result.skipped}.`);
      setSelectedArticleIds([]);
      setSelectedExpertIds([]);
      const latest = await getLabelingArticles();
      setServerItems(latest || []);
      if (importedAnnotationsByArticleId && Object.keys(importedAnnotationsByArticleId).length > 0) {
        setItems((prev) => prev.filter((row) => (latest || []).some((item) => item.article_id === row.article_id)));
      } else {
        setItems(latest || []);
      }
      if ((latest || []).length && !selectedId) {
        setSelectedId(latest[0].article_id);
      }
    } catch (e) {
      setErr(e?.response?.data?.detail || 'Bàn giao thất bại. Vui lòng thử lại.');
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="data-list-page">
      <h2 className="data-list-title">Bàn giao</h2>
      <p className="data-list-subtitle">Chọn file/text ở khung bên trái, chọn chuyên gia ở khung bên phải rồi ấn nút bàn giao.</p>
      <div className="data-list-actions-bar">
        <button type="button" className="data-list-import-btn" onClick={openImportPicker} disabled={loading || importing}>
          {importing ? 'Đang nhập...' : 'Nhập'}
        </button>
        {importedFolderName && <span className="data-list-import-hint">Folder: {importedFolderName}</span>}
      </div>
      <input
        ref={folderInputRef}
        className="data-list-folder-input"
        type="file"
        multiple
        webkitdirectory="true"
        directory="true"
        accept=".txt,.pipe,text/plain"
        onChange={handleImportFolder}
      />
      {msg && <p className="data-list-message">{msg}</p>}
      {err && <p className="data-list-error">{err}</p>}
      <div className="data-list-layout">
        <div className="data-list-table-wrap">
          <div className="data-list-quick-select">
            <div className="data-list-quick-select-title">Chọn nhanh theo STT</div>
            <div className="data-list-quick-select-form">
              <input
                type="number"
                min="1"
                placeholder="Từ"
                value={quickFrom}
                onChange={(e) => setQuickFrom(e.target.value)}
                className="data-list-quick-select-input"
              />
              <span className="data-list-quick-select-sep">-</span>
              <input
                type="number"
                min="1"
                placeholder="Đến"
                value={quickTo}
                onChange={(e) => setQuickTo(e.target.value)}
                className="data-list-quick-select-input"
              />
              <button type="button" className="data-list-quick-select-btn" onClick={applyQuickSelect} disabled={loading || items.length === 0}>
                Chọn nhanh
              </button>
            </div>
          </div>
          {loading ? (
            <p className="data-list-loading">Đang tải dữ liệu...</p>
          ) : (
            <>
              <table className="data-list-table">
                <thead>
                  <tr>
                    <th className="data-list-stt-col">STT</th>
                    <th>Tiêu đề / URL</th>
                    <th className="data-list-checkbox-col">Chọn</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, index) => (
                    <tr
                      key={item.article_id}
                      className={selectedId === item.article_id ? 'data-list-row--active' : ''}
                      onClick={() => setSelectedId(item.article_id)}
                    >
                      <td className="data-list-stt-cell">{index + 1}</td>
                      <td>
                        <div className="data-list-title-main">{item.title || item.url}</div>
                        {(item.import_annotations_count || importedAnnotationsByArticleId[item.article_id]?.length) > 0 && (
                          <span className="data-list-imported-badge">Đã có tags</span>
                        )}
                      </td>
                      <td className="data-list-checkbox-cell" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedArticleIds.includes(item.article_id)}
                          onChange={() => toggleArticle(item.article_id)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="data-list-preview-wrap data-list-preview-wrap--inner">
                <h3 className="data-list-preview-title">{selectedTitle}</h3>
                <div className="data-list-preview-content">
                  {detail?.clean_text || 'Chọn một bản ghi để xem nội dung text đã xử lý.'}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="data-list-assignee-wrap">
          <h3 className="data-list-assignee-title">Chuyên gia nhận bàn giao</h3>
          <div className="data-list-assignee-list">
            {experts.length === 0 && <p className="data-list-empty">Chưa có chuyên gia nào trong hệ thống.</p>}
            {experts.map((expert) => (
              <label key={expert.user_id} className="data-list-assignee-item">
                <input
                  type="checkbox"
                  checked={selectedExpertIds.includes(expert.user_id)}
                  onChange={() => toggleExpert(expert.user_id)}
                />
                <div>
                  <div className="data-list-assignee-name">{expert.display_name || expert.username}</div>
                  <div className="data-list-assignee-username">@{expert.username}</div>
                </div>
              </label>
            ))}
          </div>
          <button
            className="data-list-assign-btn"
            onClick={handleAssign}
            disabled={assigning || loading}
          >
            {assigning ? 'Đang bàn giao...' : 'Giao việc'}
          </button>
          <p className="data-list-helper">
            Đã chọn {selectedArticleIds.length} file/text và {selectedExpertIds.length} chuyên gia.
          </p>
        </div>
      </div>
    </div>
  );
}
