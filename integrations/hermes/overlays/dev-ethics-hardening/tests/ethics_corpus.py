"""Synthetic Ethics detector corpus. Committed before any rule, then split by hash: rules are tuned on one half only.

OWN: Ethics should take the turn. DECLINE: casual, off-topic or quoted; no read at all. REASONING: analysis about work; Reasoning owns it.
CONCERN: messages where the deterministic lane should record at least one concern.
"""
import hashlib

OWN = (
    "is it ethical to contact the recruiter's manager?",
    "is it ok to send my salary to the recruiter without asking me?",
    "is it fair to tell the recruiter I have another offer when I don't?",
    "is it okay to lie on my cover letter?",
    "is it ok to exaggerate my title on my resume?",
    "should I lie about why I left my last job in the interview?",
    "is it wrong to fake a reference for this application?",
    "should we share my private notes with the hiring manager?",
    "would it be okay to email the recruiter's boss about the rejection?",
    "is it ethical to apply for a job I plan to leave in three months?",
    "is it acceptable to inflate my salary history during the negotiation?",
    "is it ok to reach out to the interviewer on their personal phone?",
    "should I tell my manager I am interviewing elsewhere?",
    "is it appropriate to contact the hiring manager directly after being rejected?",
    "are there ethical concerns with emailing the whole team about my application?",
    "is it ok to backdate my employment on the application?",
    "should we send the client my confidential data without permission?",
    "is it right to accept an offer and keep interviewing?",
    "is it fair to withdraw my application after they made an offer?",
    "can I pretend I have a degree on my cv?",
    "is it okay to use a friend's reference without telling them?",
    "is it ethical to record the interview without telling the interviewer?",
    "should I hide the gap in my resume from the recruiter?",
    "would it be ok to delete all my application notes before the audit?",
)
DECLINE = (
    "is it ok to wear jeans?",
    "is it okay if we eat at 7?",
    "is it fair that my team lost?",
    "is this ethical?",
    "is it ok to eat pizza at midnight?",
    "is it wrong to skip the gym today?",
    "is it fair that the movie ended like that?",
    "is that okay?",
    "should we order pizza?",
    "should I lie down for a bit?",
    "any concerns about the weather tomorrow?",
    "is it ok to watch another episode?",
    "what are the risks of eating sushi?",
    "don't tell me if it's ethical to contact the recruiter",
    "the book is called \"is it ethical to lie on your resume\"",
    "translate 'is it okay to lie' into French",
    "write me a poem about whether it is fair to lie",
    "is it ok to lie to my cat?",
    "should we tell the kids about the trip?",
    "is it appropriate to wear shorts to the beach?",
    "is it right to park here?",
    "is it ok to send a birthday message to my mom?",
    "is it okay to delete old photos from my phone?",
    "is it fair to split the bill evenly?",
)
REASONING = (
    "what are the risks of accepting this offer?",
    "any concerns with this application?",
    "what are the implications of the rejection?",
    "what are the risks of negotiating the salary?",
    "should I accept this offer?",
    "any issues with the interview timeline?",
    "what are the risks of following up now?",
    "should I decline this role?",
)
CONCERN = (
    "is it ethical to contact the recruiter's manager?",
    "is it okay to lie on my cover letter?",
    "is it ok to send my salary to the recruiter without asking me?",
    "should we share my private notes with the hiring manager?",
    "is it wrong to fake a reference for this application?",
    "should I lie about why I left my last job in the interview?",
    "is it ok to exaggerate my title on my resume?",
    "would it be okay to email the recruiter's boss about the rejection?",
    "should we send the client my confidential data without permission?",
    "can I pretend I have a degree on my cv?",
)


def in_tune(message):
    return hashlib.sha256(message.encode("utf-8")).digest()[0] % 2 == 0
