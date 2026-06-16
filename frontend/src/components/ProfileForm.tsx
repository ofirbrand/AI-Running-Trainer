import { Plus, Trash2 } from "lucide-react";
import type { PersonalRecord, Profile } from "../api/types";
import { Field } from "./ui";

const COMMON_DISTANCES = ["1K", "1 mile", "5K", "10K", "Half Marathon", "Marathon"];

export function ProfileForm({
  value,
  onChange,
}: {
  value: Profile;
  onChange: (next: Profile) => void;
}) {
  function set<K extends keyof Profile>(key: K, v: Profile[K]) {
    onChange({ ...value, [key]: v });
  }

  function updatePR(idx: number, patch: Partial<PersonalRecord>) {
    const prs = [...value.personal_records];
    prs[idx] = { ...prs[idx], ...patch };
    set("personal_records", prs);
  }

  function addPR() {
    set("personal_records", [
      ...value.personal_records,
      { distance: "5K", time: "", date: "" },
    ]);
  }

  function removePR(idx: number) {
    set(
      "personal_records",
      value.personal_records.filter((_, i) => i !== idx),
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name" htmlFor="name">
          <input
            id="name"
            className="input"
            value={value.name ?? ""}
            onChange={(e) => set("name", e.target.value)}
            placeholder="Jane Runner"
          />
        </Field>
        <Field label="Gender" htmlFor="gender">
          <select
            id="gender"
            className="input"
            value={value.gender ?? ""}
            onChange={(e) => set("gender", e.target.value)}
          >
            <option value="">Prefer not to say</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Height (cm)" htmlFor="height">
          <input
            id="height"
            type="number"
            className="input"
            value={value.height_cm ?? ""}
            onChange={(e) => set("height_cm", e.target.value ? Number(e.target.value) : null)}
            placeholder="175"
          />
        </Field>
        <Field label="Weight (kg)" htmlFor="weight">
          <input
            id="weight"
            type="number"
            className="input"
            value={value.weight_kg ?? ""}
            onChange={(e) => set("weight_kg", e.target.value ? Number(e.target.value) : null)}
            placeholder="68"
          />
        </Field>
        <Field label="Date of birth" htmlFor="dob">
          <input
            id="dob"
            type="date"
            className="input"
            value={value.date_of_birth ?? ""}
            onChange={(e) => set("date_of_birth", e.target.value || null)}
          />
        </Field>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="label mb-0">Personal records</span>
          <button type="button" className="btn-ghost text-xs" onClick={addPR}>
            <Plus className="h-4 w-4" /> Add record
          </button>
        </div>
        <div className="space-y-2">
          {value.personal_records.length === 0 && (
            <p className="text-sm text-slate-400">No records yet — add your best times.</p>
          )}
          {value.personal_records.map((pr, idx) => (
            <div key={idx} className="grid grid-cols-12 items-center gap-2">
              <select
                className="input col-span-4"
                value={pr.distance}
                onChange={(e) => updatePR(idx, { distance: e.target.value })}
              >
                {COMMON_DISTANCES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
              <input
                className="input col-span-3"
                placeholder="mm:ss"
                value={pr.time ?? ""}
                onChange={(e) => updatePR(idx, { time: e.target.value })}
              />
              <input
                type="date"
                className="input col-span-4"
                value={pr.date ?? ""}
                onChange={(e) => updatePR(idx, { date: e.target.value })}
              />
              <button
                type="button"
                className="col-span-1 flex justify-center text-slate-400 transition-colors hover:text-red-600"
                onClick={() => removePR(idx)}
                aria-label="Remove record"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <Field label="General notes" htmlFor="notes" hint="Injuries, preferences, anything a coach should know.">
        <textarea
          id="notes"
          className="input min-h-[80px]"
          value={value.notes ?? ""}
          onChange={(e) => set("notes", e.target.value)}
          placeholder="e.g. recovering from a calf strain; prefer morning runs"
        />
      </Field>
    </div>
  );
}

export const EMPTY_PROFILE: Profile = {
  name: "",
  height_cm: null,
  weight_kg: null,
  gender: "",
  date_of_birth: null,
  personal_records: [],
  notes: "",
};
