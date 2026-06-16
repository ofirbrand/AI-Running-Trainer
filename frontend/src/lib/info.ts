// Concise explanations for professional terms and form fields, shown via the
// InfoTip "i" component. Kept client-side so they appear with zero latency.
export const INFO: Record<string, string> = {
  vo2max:
    "VO2 max estimates the maximum oxygen your body can use during hard effort. Higher generally means greater aerobic fitness. Your watch estimates it from recent runs.",
  resting_hr:
    "Resting heart rate is your heart rate at complete rest (best measured on waking). Lower values usually indicate better cardiovascular fitness.",
  max_hr:
    "Maximum heart rate is the highest your heart can beat during all-out effort. Used to set training heart-rate zones.",
  threshold_hr:
    "Lactate-threshold heart rate is the intensity where fatigue starts to rise sharply. Threshold runs train your ability to hold faster paces.",
  training_load:
    "Training load reflects how much training stress you've accumulated recently. It helps balance hard work with recovery.",
  longest_run:
    "Your longest single run in the last month. It helps gauge your current endurance base.",
  weekly_volume:
    "Your typical training volume per week (distance or time). The plan builds gradually from here.",
  training_frequency:
    "How many days per week you currently run. The plan respects your available days.",
  goal_pace:
    "Your target average pace for the race distance (minutes per km). Workouts are anchored around it.",
  long_run:
    "The week's key endurance run, usually at an easy, conversational pace. Builds aerobic base and durability.",
  tempo:
    "A sustained 'comfortably hard' effort around lactate threshold. Improves the pace you can hold for long periods.",
  intervals:
    "Repeated fast bouts with recovery jogs (e.g. VO2 max work). Boosts speed and aerobic power.",
  easy_run:
    "A relaxed, conversational-pace run. The bulk of training; promotes recovery and aerobic development.",
  recovery_run:
    "A very easy, short run to promote blood flow and recovery without adding stress.",
  taper:
    "Reduced training volume in the final week(s) before a race so you arrive fresh and sharp.",
  strength:
    "Resistance/strength work supports running economy and injury resistance. Note your willingness and gym access.",
  mobility:
    "Mobility and prehab routines (e.g. dynamic warm-ups, hip/ankle drills) reduce injury risk.",
  periodization:
    "Structuring training into phases (base, build, peak, taper) so fitness rises while managing fatigue.",
  reasoning_effort:
    "How much the AI 'thinks' before answering. Higher effort can yield more thoughtful plans but is slower.",
  garmin_connect:
    "Sign in with your Garmin Connect account. We store only a refreshable session token locally — never your password.",
};

export function infoFor(key: string): string | undefined {
  return INFO[key];
}
