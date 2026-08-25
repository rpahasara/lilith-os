/**
 * Isolated demo adapter for the Career module.
 *
 * Used ONLY when the real backend is unavailable during local development.
 * Every record here is clearly synthetic and must never be treated as, or
 * written back to, production data. `CareerData.isDemo` is set true so the UI
 * can surface that these are sample records.
 */
import type { Application, CareerData } from "./types";

const applications: Application[] = [
  {
    id: "app_01",
    company: "Anthropic",
    role: "Senior Product Engineer",
    stage: "final_interview",
    confidence: 82,
    sourceAccount: "gmail · primary",
    activityCount: 14,
    lastActivity: "2026-08-24T15:10:00Z",
    lastActivityLabel: "Final panel scheduled for Aug 28",
    location: "Remote",
    recruiter: { name: "Dana Whitfield", role: "Technical Recruiter", contact: "dana@…" },
    nextAction: { label: "Prep system-design panel", due: "2026-08-27" },
    followUp: false,
  },
  {
    id: "app_02",
    company: "Vercel",
    role: "Frontend Platform Engineer",
    stage: "interview",
    confidence: 71,
    sourceAccount: "linkedin",
    activityCount: 9,
    lastActivity: "2026-08-23T09:40:00Z",
    lastActivityLabel: "Completed round 2 — awaiting feedback",
    location: "Remote (US)",
    recruiter: { name: "Marcus Lee", role: "Eng Recruiting" },
    nextAction: { label: "Send thank-you + portfolio", due: "2026-08-25" },
    followUp: true,
  },
  {
    id: "app_03",
    company: "Linear",
    role: "Design Engineer",
    stage: "assessment",
    confidence: 64,
    sourceAccount: "gmail · primary",
    activityCount: 6,
    lastActivity: "2026-08-22T18:05:00Z",
    lastActivityLabel: "Take-home assessment received",
    location: "Remote (EU/US)",
    nextAction: { label: "Submit take-home", due: "2026-08-26" },
    followUp: false,
  },
  {
    id: "app_04",
    company: "Ramp",
    role: "Full-Stack Engineer",
    stage: "screening",
    confidence: 58,
    sourceAccount: "wellfound",
    activityCount: 4,
    lastActivity: "2026-08-21T13:20:00Z",
    lastActivityLabel: "Recruiter screen booked",
    location: "New York, NY",
    recruiter: { name: "Priya Nair", role: "Talent Partner" },
    nextAction: { label: "Recruiter call", due: "2026-08-25" },
    followUp: true,
  },
  {
    id: "app_05",
    company: "Supabase",
    role: "Developer Experience Engineer",
    stage: "recruiter_contact",
    confidence: 61,
    sourceAccount: "linkedin",
    activityCount: 3,
    lastActivity: "2026-08-20T11:00:00Z",
    lastActivityLabel: "Recruiter reached out via InMail",
    location: "Remote",
    recruiter: { name: "Tom Alder" },
    nextAction: { label: "Reply to recruiter", due: "2026-08-25" },
    followUp: true,
  },
  {
    id: "app_06",
    company: "Stripe",
    role: "Product Engineer, Checkout",
    stage: "applied",
    confidence: 46,
    sourceAccount: "gmail · primary",
    activityCount: 2,
    lastActivity: "2026-08-19T08:15:00Z",
    lastActivityLabel: "Application confirmed",
    location: "Remote (Global)",
  },
  {
    id: "app_07",
    company: "Notion",
    role: "Frontend Engineer",
    stage: "applied",
    confidence: 41,
    sourceAccount: "linkedin",
    activityCount: 1,
    lastActivity: "2026-08-18T16:45:00Z",
    lastActivityLabel: "Applied via referral",
    location: "San Francisco, CA",
  },
  {
    id: "app_08",
    company: "Retool",
    role: "Software Engineer",
    stage: "discovered",
    confidence: 34,
    sourceAccount: "lilith · scanner",
    activityCount: 1,
    lastActivity: "2026-08-24T07:30:00Z",
    lastActivityLabel: "Matched by job scanner (91% fit)",
    location: "Remote",
    nextAction: { label: "Review & apply" },
    followUp: false,
  },
  {
    id: "app_09",
    company: "Figma",
    role: "Senior Frontend Engineer",
    stage: "offer",
    confidence: 88,
    sourceAccount: "gmail · primary",
    activityCount: 18,
    lastActivity: "2026-08-24T20:00:00Z",
    lastActivityLabel: "Offer extended — under review",
    location: "Remote (US)",
    recruiter: { name: "Elena Ruiz", role: "Senior Recruiter" },
    nextAction: { label: "Respond to offer", due: "2026-08-29" },
    followUp: true,
  },
  {
    id: "app_10",
    company: "Datadog",
    role: "Frontend Engineer",
    stage: "rejected",
    confidence: 0,
    sourceAccount: "linkedin",
    activityCount: 5,
    lastActivity: "2026-08-15T10:00:00Z",
    lastActivityLabel: "Not moving forward after screen",
    location: "Remote",
  },
];

export function buildDemoCareerData(): CareerData {
  const active = applications.filter(
    (a) => !["rejected", "withdrawn", "closed"].includes(a.stage),
  );

  const counts = new Map<string, number>();
  for (const a of applications) counts.set(a.stage, (counts.get(a.stage) ?? 0) + 1);

  return {
    isDemo: true,
    overview: {
      totalActive: active.length,
      offers: applications.filter((a) => a.stage === "offer").length,
      interviews: applications.filter((a) =>
        ["interview", "final_interview"].includes(a.stage),
      ).length,
      responseRate: 63,
      pipelineHealth: Math.round(
        active.reduce((s, a) => s + a.confidence, 0) / Math.max(active.length, 1),
      ),
    },
    pipeline: [
      { stage: "discovered", count: counts.get("discovered") ?? 0 },
      { stage: "applied", count: counts.get("applied") ?? 0 },
      { stage: "recruiter_contact", count: counts.get("recruiter_contact") ?? 0 },
      { stage: "screening", count: counts.get("screening") ?? 0 },
      { stage: "assessment", count: counts.get("assessment") ?? 0 },
      { stage: "interview", count: counts.get("interview") ?? 0 },
      { stage: "final_interview", count: counts.get("final_interview") ?? 0 },
      { stage: "offer", count: counts.get("offer") ?? 0 },
    ],
    applications,
    activity: [
      { id: "ev1", time: "2026-08-24T20:00:00Z", text: "Figma extended an offer for Senior Frontend Engineer", company: "Figma", kind: "stage" },
      { id: "ev2", time: "2026-08-24T15:10:00Z", text: "Final panel scheduled with Anthropic", company: "Anthropic", kind: "stage" },
      { id: "ev3", time: "2026-08-24T07:30:00Z", text: "Job scanner matched Retool · Software Engineer (91% fit)", company: "Retool", kind: "system" },
      { id: "ev4", time: "2026-08-23T09:40:00Z", text: "Completed round 2 at Vercel", company: "Vercel", kind: "stage" },
      { id: "ev5", time: "2026-08-22T18:05:00Z", text: "Linear sent a take-home assessment", company: "Linear", kind: "action" },
      { id: "ev6", time: "2026-08-20T11:00:00Z", text: "Supabase recruiter reached out on LinkedIn", company: "Supabase", kind: "recruiter" },
    ],
    insights: [
      {
        id: "in1",
        title: "Decide on Figma before Anthropic's final",
        detail: "The Figma offer expires Aug 29, one day after your Anthropic panel. Consider asking Figma for a short extension.",
        tone: "risk",
      },
      {
        id: "in2",
        title: "3 follow-ups are due today",
        detail: "Vercel thank-you, Ramp recruiter call, and Supabase reply are all time-sensitive.",
        tone: "opportunity",
      },
      {
        id: "in3",
        title: "Strong momentum this week",
        detail: "2 advances and 1 new offer — pipeline health is up 8 points.",
        tone: "info",
      },
    ],
  };
}
