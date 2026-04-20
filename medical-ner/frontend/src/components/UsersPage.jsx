import React, { useState, useEffect } from 'react';
import { getUsers, createUser, updateUser, deleteUser, getRoleRequests, approveRoleRequest, rejectRoleRequest } from '../services/api';
import './UsersPage.css';

const ROLE_LABEL = { admin: 'Admin', chuyen_gia: 'Chuyên gia' };

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ username: '', password: '', display_name: '', role: 'chuyen_gia' });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [roleRequests, setRoleRequests] = useState([]);
  const [requestsLoading, setRequestsLoading] = useState(true);
  const [requestsError, setRequestsError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ display_name: '', role: 'labeler', password: '' });
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
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createUser(form);
      setUsers((prev) => [...prev, created]);
      setForm({ username: '', password: '', display_name: '', role: 'labeler' });
    } catch (err) {
      setCreateError(err.response?.data?.detail || 'Tạo thất bại.');
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (user) => {
    setEditingId(user.user_id);
    setEditForm({
      display_name: user.display_name || '',
      role: user.role,
      password: '',
    });
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditError(null);
  };

  const saveEdit = async (userId) => {
    setEditError(null);
    try {
      const payload = {
        display_name: editForm.display_name,
        role: editForm.role,
      };
      if (editForm.password.trim()) {
        payload.password = editForm.password.trim();
      }
      const updated = await updateUser(userId, payload);
      setUsers((prev) => prev.map((u) => (u.user_id === userId ? updated : u)));
      setEditingId(null);
    } catch (err) {
      setEditError(err.response?.data?.detail || 'Không thể cập nhật user.');
    }
  };

  const handleDelete = async (userId) => {
    const ok = window.confirm('Bạn có chắc muốn xóa tài khoản này?');
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
      <div className="users-table-wrap">
        {loading && <p className="users-loading">Đang tải...</p>}
        {error && <p className="users-error">{error}</p>}
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
                <tr key={u.user_id}>
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
                      <select
                        className="users-select users-select--inline"
                        value={editForm.role}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, role: e.target.value }))}
                      >
                        <option value="labeler">Labeler</option>
                        <option value="chuyen_gia">Chuyên gia</option>
                        <option value="admin">Admin</option>
                      </select>
                    ) : (
                      <span className={`users-role-badge users-role-badge--${u.role}`}>
                        {ROLE_LABEL[u.role] || u.role}
                      </span>
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
                        />
                        <button className="users-request-btn users-request-btn--approve" onClick={() => saveEdit(u.user_id)}>Lưu</button>
                        <button className="users-request-btn users-request-btn--reject" onClick={cancelEdit}>Hủy</button>
                      </div>
                    ) : (
                      <div className="users-actions-inline">
                        <button className="users-request-btn users-request-btn--approve" onClick={() => startEdit(u)}>Sửa</button>
                        <button className="users-request-btn users-request-btn--reject" onClick={() => handleDelete(u.user_id)}>Xóa</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {editError && <p className="users-error">{editError}</p>}
      </div>

      <div className="users-create-form-wrap">
        <h3 className="users-create-title">Thêm người dùng</h3>
        <form className="users-create-form" onSubmit={handleCreate}>
          <input
            className="users-input"
            placeholder="Tên đăng nhập *"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <input
            className="users-input"
            placeholder="Mật khẩu *"
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <input
            className="users-input"
            placeholder="Tên hiển thị"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
          <select
            className="users-select"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            <option value="labeler">Labeler</option>
            <option value="chuyen_gia">Chuyên gia</option>
            <option value="admin">Admin</option>
          </select>
          {createError && <p className="users-error">{createError}</p>}
          <button className="users-create-btn" type="submit" disabled={creating}>
            {creating ? 'Đang tạo...' : 'Tạo'}
          </button>
        </form>
      </div>

      <div className="users-requests-wrap">
        <h3 className="users-create-title">Yêu cầu nâng quyền</h3>
        {requestsLoading && <p className="users-loading">Đang tải...</p>}
        {requestsError && <p className="users-error">{requestsError}</p>}
        {!requestsLoading && roleRequests.length === 0 && (
          <p className="users-loading">Không có yêu cầu nào.</p>
        )}
        {roleRequests.map((req) => (
          <div key={req.id} className="users-request-row">
            <div className="users-request-info">
              <span className="users-request-name">{req.display_name || req.username}</span>
              <span className="users-request-username">@{req.username}</span>
            </div>
            <div className="users-request-actions">
              <button
                className="users-request-btn users-request-btn--approve"
                onClick={() => handleApprove(req.id)}
              >
                Duyệt
              </button>
              <button
                className="users-request-btn users-request-btn--reject"
                onClick={() => handleReject(req.id)}
              >
                Từ chối
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
