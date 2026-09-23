<!-- ai-generated: 60% - Claude Code drafted the justifications; I picked which tools to deny and edited the wording. -->
# Agent policy

`.claude/agents/reviewer.md` is a read-only review sub-agent. Its `disallowedTools` denylist is a set of
blast-radius decisions: each entry names an action whose consequence should stay in a human's hands, not fall out
of asking an agent for a review.

- Bash(rm *): the reviewer reads and comments; deleting files is the author's decision, not the reviewer's, and a review that can delete evidence of what it reviewed is not trustworthy
- Bash(git push *): publishing a commit or a tag changes shared, public state (this repository is graded from receipted tags); a reviewer must never be able to make that call on its own
- Bash(docker *): building or running the service is how a change gets verified, which is a separate, deliberate step from reading and commenting, and running arbitrary containers is a large blast radius for a review task
- WebFetch: the reviewer's job is this repository's own files against the course documents already in doc/lab1/; it has no reason to reach the network, and denying it removes an entire class of exfiltration or prompt-injection risk
