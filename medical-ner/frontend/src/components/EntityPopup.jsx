import { useEffect } from 'react';
import { ENTITY_CONFIG } from '../config/entityConfig';
import './EntityPopup.css';

const ENTITY_TYPES = [
  { key: 'DISEASE', label: 'Bệnh' },
  { key: 'DRUG', label: 'Thuốc' },
  { key: 'SYMPTOM', label: 'Triệu chứng' },
  { key: 'TREATMENT', label: 'Điều trị' },
  { key: 'BODY_PART', label: 'Bộ phận' },
  { key: 'TEST', label: 'Xét nghiệm' }
];

const EntityPopup = ({ mode, currentType, position, onSelect, onDelete, onClose }) => {
  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (e.target.closest('.entity-popup') === null) {
        onClose();
      }
    };

    // Delay to avoid immediate close from the click that opened popup
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onClose]);

  // Clamp position to viewport
  const clampedPosition = {
    x: Math.min(Math.max(position.x, 10), window.innerWidth - 260),
    y: Math.min(Math.max(position.y, 10), window.innerHeight - 400)
  };

  return (
    <div
      className="entity-popup"
      style={{
        left: `${clampedPosition.x}px`,
        top: `${clampedPosition.y}px`
      }}
    >
      <div className="entity-popup-header">
        Chọn loại thực thể
      </div>

      <div className="entity-popup-options">
        {ENTITY_TYPES.map(({ key, label }) => {
          const config = ENTITY_CONFIG[key];
          const isSelected = currentType === key;

          return (
            <div
              key={key}
              className={`entity-popup-option ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelect(key)}
              style={{
                borderLeft: `4px solid ${config.border}`,
              }}
            >
              <div
                className="entity-popup-dot"
                style={{
                  backgroundColor: config.border
                }}
              />
              <span style={{ color: config.text }}>{label}</span>
              {isSelected && <span className="entity-popup-checkmark">✓</span>}
            </div>
          );
        })}
      </div>

      {mode === 'edit' && (
        <>
          <div className="entity-popup-divider" />
          <div
            className="entity-popup-delete"
            onClick={onDelete}
          >
            🗑️ Xóa thực thể
          </div>
        </>
      )}
    </div>
  );
};

export default EntityPopup;
