import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { profileApi } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { Banner, PageLoader, Spinner } from "../components/ui";
import { EMPTY_PROFILE, ProfileForm } from "../components/ProfileForm";
import { GarminConnect } from "../components/GarminConnect";
import type { Profile } from "../api/types";

export function ProfilePage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  const [profile, setProfile] = useState<Profile>({ ...EMPTY_PROFILE });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setProfile({ ...EMPTY_PROFILE, ...data, personal_records: data.personal_records ?? [] });
  }, [data]);

  const mutation = useMutation({
    mutationFn: () => profileApi.update(profile),
    onSuccess: () => {
      setSaved(true);
      void qc.invalidateQueries({ queryKey: ["profile"] });
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isLoading) return <PageLoader />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Your profile</h1>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card p-6 lg:col-span-2">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">Runner details</h2>
          {mutation.isError && <Banner kind="error">{apiErrorMessage(mutation.error)}</Banner>}
          {saved && <Banner kind="success">Profile saved.</Banner>}
          <div className="mt-2">
            <ProfileForm value={profile} onChange={setProfile} />
          </div>
          <div className="mt-6">
            <button
              className="btn-primary"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
            >
              {mutation.isPending && <Spinner />} Save changes
            </button>
          </div>
        </div>

        <div className="card h-fit p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">Garmin</h2>
          <GarminConnect />
        </div>
      </div>
    </div>
  );
}
