"""Planning intent corpus, committed before the rule. TEST_ONLY, synthetic. Same split rule as the Reasoning pools:

    in_tune(m) True   may be read and used while changing rules
    in_tune(m) False  never read during tuning; scored once, at the end, and its failures are reported, not fixed

Labels are fixed here. WORK must match. CASUAL, NEGATED and YIELDS must not: YIELDS belong to another lane.
"""

import hashlib

WORK = [
    "plan how to follow up on application 14", "make a plan for the job search", "plan the steps for my interview preparation", "draw up a plan for the salary negotiation",
    "come up with a plan to chase the recruiter", "outline the steps to accept this offer", "map out the next month of the job search", "what would we need to do to get application 7 moving?",
    "what steps are needed for the Oslo role?", "how would you approach the second interview?", "what's the plan for application 21?", "plan out how to respond to the rejection",
    "sketch a plan for the cover letter", "lay out the steps for this offer", "devise a plan to get an interview at Acme", "plan how to negotiate the offer but don't do anything yet",
    "plan a follow-up for application 3 but do not send it", "outline a plan for applying to role 9", "what would I need to do in order to accept the job?", "how would we go about withdrawing application 11?",
    "plan the next steps on the recruiter", "make a plan for the hiring manager interview", "what's the plan to close out application 2?", "plan for the deadline on role 6",
    "come up with a plan for the offer", "map out how to prepare for the interview", "outline the approach for the job search", "draw up a plan to respond to the recruiter",
]

CASUAL = [
    "make a plan for dinner", "plan a birthday party", "plan out our holiday", "what's the plan for tonight?", "what's the plan for the weekend?", "come up with a plan for the garden",
    "outline the steps to bake bread", "map out the route to the airport", "how would you approach a chess endgame?", "plan to meet at noon", "plan how to clean the garage", "make a plan to run a 10k",
    "draw up a plan for the kitchen renovation", "what would I need to do to get a passport?", "what steps are needed to change a tyre?", "plan for the film night", "sketch a plan for the treehouse",
    "lay out the steps for the recipe", "how would we go about moving house?", "devise a plan to beat this game level", "plan a trip to Lisbon", "what would we need to do to adopt a cat?",
    "plan the menu", "make a plan for the school run", "plan my workout", "what's the plan for lunch?", "how would you approach learning piano?", "come up with a plan for the party playlist",
]

NEGATED = [
    "don't plan the follow-up for application 3", "no need to plan the job search", "stop planning the interview", "never mind the plan for the offer", "skip the plan for application 8",
    "I'm not asking you to make a plan for the recruiter", "forget about planning the salary negotiation", "you don't need to outline the steps for this offer",
    "please don't map out the job search", "not looking to make a plan for role 4", "don't draw up a plan for the offer", "leave the plan for the interview",
]

YIELDS = [
    "track application 6 as a goal", "which goal has priority?", "what is pending right now?", "draft a follow-up for application 9", "what is blocked right now?", "what are you working on?",
    "what is the plan for my goals?", "show me the current goals",
]


def in_tune(message):
    return hashlib.sha256(message.encode("utf-8")).digest()[0] % 2 == 0
