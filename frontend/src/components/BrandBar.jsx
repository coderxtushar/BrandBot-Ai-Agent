import { Plus, Trash2 } from 'lucide-react';
import { NEW_BRAND } from '../lib/brands';

export default function BrandBar({ brands, activeId, onSelect, onDelete, disabled }) {
  const isNew = activeId === NEW_BRAND;
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="brand-switch" className="sr-only">Brand</label>
      <select
        id="brand-switch"
        className="field mt-0 w-40 sm:w-56"
        value={activeId ?? ''}
        onChange={(e) => onSelect(e.target.value)}
        disabled={disabled}
      >
        {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        {isNew && <option value={NEW_BRAND}>New brand…</option>}
      </select>
      {!isNew && (
        <>
          <button
            type="button"
            className="btn-ghost px-2.5"
            onClick={() => onSelect(NEW_BRAND)}
            disabled={disabled}
            aria-label="New brand"
            title="New brand"
          >
            <Plus className="size-4" />
          </button>
          <button
            type="button"
            className="btn-ghost px-2.5 hover:text-red-600"
            onClick={onDelete}
            disabled={disabled}
            aria-label="Delete brand"
            title="Delete brand"
          >
            <Trash2 className="size-4" />
          </button>
        </>
      )}
    </div>
  );
}
