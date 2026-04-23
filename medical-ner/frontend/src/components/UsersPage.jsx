import React, { useState, useEffect } from 'react';
import { getUsers, createUser, updateUser, deleteUser, getRoleRequests, approveRoleRequest, rejectRoleRequest } from '../services/api';
import './UsersPage.css';

const ROLE_LABEL = { admin: 'Admin', chuyen_gia: 'Chuyên gia', reviewer: 'Reviewer' };
const ROLE_OPTIONS = ['chuyen_gia', 'reviewer', 'admin'];

const parseRoles = (user) => {
  if (Array.isArray(user?.roles) && user.roles.length > 0) return user.roles;
  if (typeof user?.role === 'string' && user.role.trim()) {
    return user.role.split(',').map((r) => r.trim()).filter(Boolean);
  }
  return ['chuyen_gia'];
};

const toggleRole = (roles, role) => {
  return roles.includes(role)
    ? roles.filter((r) => r !== role)
    : [...roles, role];
};

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ username: '', password: '', display_name: '', roles: ['chuyen_gia'] });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [roleRequests, setRoleRequests] = useState([]);
  const [requestsLoading, setRequestsLoading] = useState(true);
  const [requestsError, setRequestsError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ display_name: '', roles: ['chuyen_gia'], password: '' });
  const [editError, setEditError] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      setUsers(await getUsers());
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    loadRequests();
  }, []);

  const loadRequests = async () => {
    setRequestsLoading(true);
    try {
      setRoleRequests(await getRoleRequests());
    } catch {
      setRequestsError('Không thể tải yêu cầu.');
    } finally {
      setRequestsLoading(false);
    }
  };

  const handleApprove = async (requestId) => {
    try {
      await approveRoleRequest(requestId);
      setRoleRequests((prev) => prev.filter((r) => r.id !== requestId));
    } catch (err) {
      setRequestsError(err.response?.data?.detail || 'Lỗi duyệt.');
    }
  };

  const handleReject = async (requestId) => {
    try {
      await rejectRoleRequest(requestId);
      setRoleRequests((prev) => prev.filter((r) => r.id !== requestId));
    } catch (err) {
      setRequestsError(err.response?.data?.detail || 'Lỗi từ chối.');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password.trim()) {
      setCreateError('Vui lòng điền đầy đủ.');
      return;
    }
    if ((form.roles || []).length === 0) {
      setCreateError('Vui lòng chọn ít nhất 1 quyền.');
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createUser(form);
      setUsers((prev) => [...prev, created]);
      setForm({ username: '', password: '', display_name: '', roles: ['chuyen_gia'] });
    } catch (err) {
      setCreateError(err.response?.data?.detail || 'Tạo thất bại.');
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (user) => {
    setEditingId(user.user_id);
    setEditForm({ display_name: user.display_name || '', roles: parseRoles(user), password: '' });
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditError(null);
  };

  const saveEdit = async (userId) => {
    setEditError(null);
    if ((editForm.roles || []).length === 0) {
      setEditError('Vui lòng chọn ít nhất 1 quyền.');
      return;
    }
    try {
      const payload = { display_name: editForm.display_name, roles: editForm.roles };
      if (editForm.password.trim()) payload.password = editForm.password.trim();
      const updated = await updateUser(userId, payload);
      setUsers((prev) => prev.map((u) => (u.user_id === userId ? updated : u)));
      setEditingId(null);
    } catch (err) {
      setEditError(err.response?.data?.detail || 'Không thể cập nhật user.');
    }
  };

  const handleDelete = async (userId) => {
    const ok = window.confirm('Bạn có chắc muốn xóa tài khoản này? Tài khoản sẽ mất quyền truy cập, nhưng toàn bộ dữ liệu đã tạo vẫn được giữ nguyên.');
    if (!ok) return;
    try {
      await deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.user_id !== userId));
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể xóa tài khoản.');
    }
  };

  return (
    <div className="users-page">

      {/* ── User table ── */}
      <div className="users-table-wrap">
        <div className="users-section-header">
          <h3 className="users-section-title">Danh sách người dùng</h3>
          {!loading && <span className="users-count-badge">{users.length} người dùng</span>}
        </div>

        {loading && <p className="users-loading">Đang tải...</p>}
        {error   && <p className="users-error">{error}</p>}

        {!loading && !error && (
          <table className="users-table">
            <thead>
              <tr>
                <th>Tên hiển thị</th>
                <th>Tên đăng nhập</th>
                <th>Quyền</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className={editingId === u.user_id ? 'users-row--editing' : ''}>
                  <td>
                    {editingId === u.user_id ? (
                      <input
                        className="users-input users-input--inline"
                        value={editForm.display_name}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, display_name: e.target.value }))}
                      />
                    ) : (u.display_name || '—')}
                  </td>
                  <td className="users-username">{u.username}</td>
                  <td>
                    {editingId === u.user_id ? (
                      <div className="users-actions-inline">
                        {ROLE_OPTIONS.map((role) => (
                          <label key={role} className="users-request-username">
                            <input
                              type="checkbox"
                              checked={editForm.roles.includes(role)}
                              onChange={() => setEditForm((prev) => ({ ...prev, roles: toggleRole(prev.roles, role) }))}
                              disabled={u.is_active === false}
                            />{' '}
                            {ROLE_LABEL[role] || role}
                          </label>
                        ))}
                      </div>
                    ) : (
                      <div className="users-actions-inline">
                        {parseRoles(u).map((role) => (
                          <span key={`${u.user_id}-${role}`} className={`users-role-badge users-role-badge--${role}`}>
                            {ROLE_LABEL[role] || role}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    {editingId === u.user_id ? (
                      <div className="users-actions-inline">
                        <input
                          className="users-input users-input--inline"
                          type="password"
                          placeholder="Mật khẩu mới (tuỳ chọn)"
                          value={editForm.password}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, password: e.target.value }))}
                          disabled={u.is_active === false}
                        />
                        <button className="users-btn users-btn--save" onClick={() => saveEdit(u.user_id)} disabled={u.is_active === false}>Lưu</button>
                        <button className="users-btn users-btn--cancel" onClick={cancelEdit}>Hủy</button>
                      </div>
                    ) : (
                      <div className="users-actions-inline">
                        <button className="users-btn users-btn--edit" onClick={() => startEdit(u)} disabled={u.is_active === false}>Sửa</button>
                        <button className="users-btn users-btn--delete" onClick={() => handleDelete(u.user_id)} disabled={u.is_active === false}>Xóa</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {editError && <p className="users-error users-error--inline">{editError}</p>}
      </div>

      <div className="users-bottom-grid">
        {/* ── Create form ── */}
        <div className="users-create-form-wrap">
          <div className="users-section-header">
            <h3 className="users-section-title">Thêm người dùng</h3>
          </div>
          <form className="users-create-form" onSubmit={handleCreate}>
            <div className="users-field">
              <label className="users-label">Tên đăng nhập <span className="users-required">*</span></label>
              <input
                className="users-input"
                placeholder="username"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
            <div className="users-field">
              <label className="users-label">Mật khẩu <span className="users-required">*</span></label>
              <input
                className="users-input"
                placeholder="••••••••"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div className="users-field">
              <label className="users-label">Tên hiển thị</label>
              <input
                className="users-input"
                placeholder="Nguyễn Văn A"
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              />
            </div>
            <div className="users-field">
              <label className="users-label">Quyền</label>
              <div className="users-actions-inline">
                {ROLE_OPTIONS.map((role) => (
                  <label key={role} className="users-request-username">
                    <input
                      type="checkbox"
                      checked={form.roles.includes(role)}
                      onChange={() => setForm((prev) => ({ ...prev, roles: toggleRole(prev.roles, role) }))}
                    />{' '}
                    {ROLE_LABEL[role] || role}
                  </label>
                ))}
              </div>
            </div>
            {createError && <p className="users-error users-error--form">{createError}</p>}
            <button className="users-create-btn" type="submit" disabled={creating}>
              {creating ? 'Đang tạo...' : '+ Tạo tài khoản'}
            </button>
          </form>
        </div>

        {/* ── Role requests ── */}
        <div className="users-requests-wrap">
          <div className="users-section-header">
            <h3 className="users-section-title">Yêu cầu nâng quyền</h3>
            {roleRequests.length > 0 && (
              <span className="users-count-badge users-count-badge--alert">{roleRequests.length}</span>
            )}
          </div>
          {requestsLoading && <p className="users-loading">Đang tải...</p>}
          {requestsError  && <p className="users-error">{requestsError}</p>}
          {!requestsLoading && roleRequests.length === 0 && (
            <p className="users-empty">Không có yêu cầu nào.</p>
          )}
          <div className="users-request-list">
            {roleRequests.map((req) => (
              <div key={req.id} className="users-request-row">
                <div className="users-request-info">
                  <span className="users-request-name">{req.display_name || req.username}</span>
                  <span className="users-request-username">@{req.username}</span>
                </div>
                <div className="users-request-actions">
                  <button className="users-btn users-btn--save" onClick={() => handleApprove(req.id)}>Duyệt</button>
                  <button className="users-btn users-btn--delete" onClick={() => handleReject(req.id)}>Từ chối</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}