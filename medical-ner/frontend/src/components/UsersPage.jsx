import React, { useState, useEffect } from 'react';
import { getUsers, createUser } from '../services/api';
import './UsersPage.css';

const ROLE_LABEL = { admin: 'Admin', chuyen_gia: 'Chuyên gia', labeler: 'Labeler' };

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ username: '', password: '', display_name: '', role: 'labeler' });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);

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

  useEffect(() => { load(); }, []);

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
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id}>
                  <td>{u.display_name || '—'}</td>
                  <td className="users-username">{u.username}</td>
                  <td>
                    <span className={`users-role-badge users-role-badge--${u.role}`}>
                      {ROLE_LABEL[u.role] || u.role}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
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
    </div>
  );
}
