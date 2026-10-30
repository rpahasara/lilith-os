"""Third validation pool: the final conservative review, committed before any change to the rule. TEST_ONLY, synthetic. Same author and split as before:

    in_tune(m) True   may be read and used while changing rules
    in_tune(m) False  never read during tuning; scored once, at the end, and its failures are reported, not fixed

Labels are fixed here. PARAPHRASE must match. FALSE_MATCH and NEGATED must not. PRECEDENCE messages belong to another lane, so Reasoning must yield.
"""

import hashlib

PARAPHRASE = [
    "how would you approach application 19?", "what would you recommend on the Madrid offer?", "does taking this job make any sense for me?",
    "help me figure out what to do about the recruiter", "talk me through whether to accept the offer", "how worried should I be about application 2?",
    "what do you think went wrong in the interview?", "is it worth pushing back on the salary?", "should I still bother with application 27?",
    "what's the smart play on this offer?", "how can I improve my chances at role 5?", "why might the recruiter have gone silent?",
    "what am I missing about this job?", "can you weigh up the salary against the commute for this role?", "how does this offer compare to my current job?",
    "what could go wrong if I accept the offer?", "is the hiring manager stalling?", "do you reckon the interview went okay?",
    "how should I prioritize these applications?", "which of the two offers would you pick?", "what's the catch with this offer?",
    "should I ask for more on the salary?", "why do you think they rejected application 13?", "what's my best move after this rejection?",
    "could you sanity-check my plan for the interview?", "how likely is an offer on application 30?", "is my cover letter strong enough?",
    "what should I focus on before the interview?", "explain what this rejection means for the job search", "where is the risk in this offer?",
]

FALSE_MATCH = [
    "the recruiter called me today", "I got the offer!", "my interview went well", "applications close on Friday", "the job is in Oslo",
    "thanks for the help with the application", "my friend got a job offer", "I sent the cover letter", "the salary is 70k", "just finished the interview",
    "what stage is application 12 at?", "what's the status of the Oslo role?", "what round is the interview?", "how long is the interview?", "who interviewed me at Acme?",
    "when did I apply to role 9?", "where did I save the cover letter?", "what email did the recruiter use?", "which day is the deadline?", "what time zone is the interview in?",
    "is the shop having a job lot sale?", "what's a good offer on a used car?", "how do I fill in a passport application?", "what's the role of mitochondria?", "any special offers at the bakery?",
    "what's the job of a goalkeeper?", "should I offer them tea?", "how do I play the role of Hamlet?", "what's a good job for a rainy day around the house?", "who is the salary cap for in the NBA?",
    "what's the deadline for tax returns?", "how was your interview with the mayor on TV?", "does this app have a dark mode?", "is the application crashing on your phone?", "should I reject this cookie banner?",
]

NEGATED = [
    "don't analyze the offer yet", "I'm not asking for options on application 3", "never mind what's blocking job 7", "no need to assess the role",
    "stop evaluating application 9", "don't tell me what to do about the recruiter", "I didn't ask whether the offer is good", "skip the analysis of the interview",
    "forget about my options on role 2", "not looking for advice on the salary", "please don't compare the offers", "no analysis of the rejection, thanks",
    "you don't need to weigh the job", "I'm not wondering why the recruiter went quiet", "leave aside what's blocking the application", "without analyzing the offer, just say hi",
]

PRECEDENCE = [
    "draft a follow-up for application 9", "write a thank-you note to the recruiter", "reply to the recruiter about application 4", "follow up on application 22",
    "which goal has priority?", "what are you working on?", "what is blocked right now?", "track application 6 as a goal",
    "what is pending right now?", "what's on hold?",
]


def in_tune(message):
    return hashlib.sha256(message.encode("utf-8")).digest()[0] % 2 == 0
