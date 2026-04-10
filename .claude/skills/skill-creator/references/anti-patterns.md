# Skill Anti-Patterns

Ten common failure modes from production skill audits. Each pattern includes how to detect it and what to do instead.

---

## 1. The Silent Skill
**Symptom**: Skill never activates automatically. Users must invoke it with `/skill-name` every time.
**Fix**: Rewrite the description with "Use when" trigger language listing 3+ specific scenarios. Add "even if they don't explicitly ask for" + synonyms. Front-load triggers within 250 characters.

## 2. The Noisy Skill
**Symptom**: Skill fires on unrelated requests because description keywords are too broad.
**Fix**: Add "NOT for" exclusions. Use domain-specific terms instead of generic ones. Test with near-miss queries that should NOT trigger.

## 3. The Redundant Skill
**Symptom**: Claude already handles this task well without the skill. Adding the skill makes output worse or identical.
**Fix**: Run tasks without the skill first. Only create a skill for gaps where Claude fails. If the base model passes at a comparable rate, the skill is unnecessary.

## 4. The Token Hog
**Symptom**: Skill body is 400+ lines. Instructions repeat information Claude already knows. Response quality does not justify the context cost.
**Fix**: Move detailed content to references/. Keep SKILL.md body under 300 lines. Use scripts for deterministic operations (zero context cost). Only teach what Claude does not already know.

## 5. The Stub Skill
**Symptom**: validate.sh contains `echo "OK" && exit 0`. main_helper.py prints a placeholder. Scripts exist but do nothing real.
**Fix**: validate.sh must check something domain-specific (syntax, format, constraints, lengths). main_helper.py must do real deterministic work (parsing, formatting, extraction). If there is nothing to validate, reconsider whether the skill needs scripts.

## 6. The Broken Reference
**Symptom**: SKILL.md references files that do not exist. Paths are wrong, files were moved, or assets were never created. 73% of audited community skills had this issue.
**Fix**: Use `${CLAUDE_SKILL_DIR}/` for all paths. After creating the package, verify every path in SKILL.md resolves to a real file. Validate references in CI.

## 7. The Nested Labyrinth
**Symptom**: References point to other references that point to more references. Claude loses context after one level of indirection.
**Fix**: Keep all references one level deep from SKILL.md. If a reference needs sub-references, inline the critical content. Files over 100 lines should have a table of contents at the top.

## 8. The Cookie Cutter
**Symptom**: All generated skills look identical. Examples are generic. Validation is boilerplate. The skill adds no domain-specific value.
**Fix**: Examples must use realistic domain language. Validation must check domain-specific constraints. The guide.md must contain actual domain knowledge. If you cannot write domain-specific content for these, the skill is too generic.

## 9. The Instruction Overloader
**Symptom**: Body contains 30+ MUSTs, SHOULDs, and NEVER directives. Claude drops random instructions when overloaded (not just the new ones -- it degrades uniformly across ALL instructions).
**Fix**: Prioritize. Keep critical rules to under 10. Use examples to teach style instead of rules. Replace prescriptive instructions with goals and constraints. Use scripts for anything that can be validated deterministically.

## 10. The Stale Skill
**Symptom**: Skill was written for an older model. Current model already incorporates the techniques natively, or the skill conflicts with improved default behavior.
**Fix**: Re-run evals periodically (every model release). Compare skill-loaded vs skill-unloaded performance. If the base model matches or exceeds skill-loaded quality, retire the skill.
