"""Second validation pool, committed before the look-up rule. TEST_ONLY, synthetic. Same author and same split rule as validation_pool.py:

    in_tune(m) True   may be read and used while changing rules
    in_tune(m) False  never read during tuning; scored once, at the end, and its failures are reported, not fixed

Labels are fixed here. Editing one to make a result pass is not allowed.
LOOKUP is a work question that wants one stored fact. ANALYTIC wants judgement. CASUAL is not about work.
"""

import hashlib

ANALYTIC = [
    "is the Berlin offer worth taking?", "does this job fit what I want?", "who should I ask about the role?", "which offer is better?",
    "which application looks strongest?", "where did my application go wrong?", "is it too late to follow up on application 3?",
    "was rejecting the offer a bad call?", "did I undersell myself in the interview?", "are my salary expectations too high?",
    "is application 22 still worth chasing?", "does the recruiter seem interested?", "should I accept before the deadline?",
    "how bad is this rejection for me?", "why is the hiring manager so quiet?", "what does the silence on role 4 tell us?",
    "what's the risk of negotiating this offer?", "what's the best next move on the job search?", "what's holding application 18 back?",
    "can you help me think through this offer?", "could you weigh these two jobs for me?", "would you take this job?",
    "tell me what you'd change in the cover letter", "help me prepare for the interview", "walk me through the trade-offs of this offer",
    "explain why the interview might have gone wrong", "any red flags in this offer?", "are they likely to make an offer?",
    "do I have a real chance at role 6?", "is the salary fair for this role?", "where should I focus the job search?",
    "who is the stronger reference for this application?", "was it wrong to follow up so soon?", "does the deadline leave me enough time?",
    "is this rejection final or worth appealing?", "which role should I prioritize?", "what's your honest view of the interview?",
    "what's the smartest reply to the recruiter?", "how should I read this rejection?", "is this job a step backward?",
]

LOOKUP = [
    "who is my recruiter at Acme?", "who was the interviewer?", "who sent the offer?", "where is the Oslo interview?", "where was the job posted?",
    "which company made the offer?", "which recruiter emailed me?", "what's the job location?", "what's the salary for role 7?", "what is the deadline?",
    "what's the hiring manager's name?", "what is the role called?", "is the interview on Friday?", "is application 31 closed?", "is the offer in writing?",
    "was the offer accepted?", "was application 16 submitted?", "did the recruiter call?", "did the rejection email come?", "did I apply to role 8?",
    "does the job have a bonus?", "does role 2 require travel?", "are the interviews online?", "are there two interview rounds?", "was the cover letter attached?",
    "what's the status of application 12?", "what stage is application 40 at?", "who's the contact for this offer?", "what's the follow-up date?", "is the job remote?",
    "what company is the role at?", "do I have an interview this week?", "has the recruiter replied?", "have they sent the offer?", "which date is the interview?",
]

CASUAL = [
    "where is the good coffee near the office?", "is it raining?", "who won last night?", "what's the capital of Peru?", "did you sleep well?",
    "which pizza should we order?", "how was your weekend?", "is the bakery open?", "what's for dinner?", "who is your favourite author?",
    "should I get a haircut?", "can you tell me a joke?", "does this shirt look okay?", "why is the sky blue?", "are you there?",
]


def in_tune(message):
    return hashlib.sha256(message.encode("utf-8")).digest()[0] % 2 == 0
