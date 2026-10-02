# Claude Model Selection Guide
> Ported from revfactory/harness v2.1.0 (Apache-2.0), translated to English and adapted for FinHub. Original: https://github.com/revfactory/harness

Choose the model for an agent by four criteria: the **complexity, expected duration, required autonomy, and response speed** of its work. You can set the model in `model:` in the YAML frontmatter of the agent definition file, in the `model` parameter of the `Agent` tool, and in `opts.model` passed to `agent()` in `Workflow`. Record the reason for your choice as a comment in the agent definition or the orchestration skill.

## Summary decision table

| Model | Selection criteria | Representative work |
|------|----------|----------|
| **fable** | A long-running, autonomous model that plans for itself from a complex goal and carries multiple steps through to the final deliverable | Hard reasoning, creative work, agent orchestration, very difficult work that must be entrusted from planning through long-running execution |
| **opus** | A reasoning-focused model that analyzes specialized, complex problems in depth and reaches refined judgments and conclusions | Design and architecture, code generation, complex analysis, cross-verification, creative writing |
| **sonnet** | A general-purpose model that handles most everyday work in a balanced way: writing, coding, analysis, research | General writing, coding, and research; log parsing, format conversion, static file checks, running deploy scripts, simple collection |

## 1. Fable

**Main role:** Suited to very difficult work that must be planned and carried out autonomously over a long period. It does not stop at answering a question directly; it understands the goal, plans multiple steps, and carries them through to the final deliverable.

### Work it suits

**1. Long-running work with chained steps.** Use it when the work does not end with a single answer and several tasks must be performed in sequence.
- Market research → competitor analysis → strategy formulation → report writing
- Requirements analysis → service architecture design → development plan → producing deliverables
- Reviewing several documents, then deriving an overall conclusion and an execution plan
- Designing the whole process of a long project

What matters is that the individual steps are not isolated: **the result of an earlier step affects the next step.**

**2. Reviewing large, complex material.** Use it when you must review a large volume of complex material together, such as papers, reports, meeting minutes, and technical documents, and the job goes beyond a plain summary into the next task.
- Analyzing commonalities and differences across several sources
- Identifying claims that conflict
- Separating core evidence from peripheral information
- Synthesizing a lot of material into a single logical deliverable

**3. Turning a vague idea into a concrete deliverable.** This is work where the requirements are not fixed and only a rough idea is given, and the model decides the necessary details itself and produces the deliverable.
- Developing the idea of "a service with this kind of feel" into a business plan
- Designing the structure and content of a presentation from only a rough topic
- Turning an incomplete product idea into a feature list and a development plan
- Producing a finished report or content when there is no draft

Choose it when **the ability to judge and fill in the missing parts** matters more than the ability to follow fixed instructions exactly.

**4. Problems that need deep reasoning together with planning, coordination, and long-running execution.** Fable does not unconditionally reason more deeply than Opus. Fable is better suited to problems that need planning, coordination, and long-running execution along with deep reasoning.

### When to choose Fable

- When getting the result requires going through several steps
- When it is hard for the user to specify every procedure
- When the model must plan the order of work itself
- When a finished deliverable must be produced from a vast body of material
- When a project-level result is needed rather than a short answer

## 2. Opus

**Main role:** A high-performance reasoning model that analyzes and solves difficult problems in depth. Where Fable suits long-term planning and autonomous execution, Opus suits digging deeply into a problem with a defined scope and analyzing it logically.

### Work it suits

**1. Complex research and analysis.** This is work that does not end with finding information: it must weigh several pieces of evidence and reach a logical conclusion.
- Researching a complex industry or market in depth
- Comparative analysis of several research results
- Evaluating the pros and cons of a policy or business strategy
- Analyzing causes and effects from data and documents
- Writing a conclusion that synthesizes differing perspectives

**2. Reviewing long technical documents.** This is work that reads and understands documents with heavy terminology and complex structure. Software design documents, system architecture documents, research papers, technical specifications, product requirements documents, and complex API and development documents all qualify. It suits **grasping logical structure and technical meaning** more than shortening a document.

**3. Reviewing research methodology.** This is work that weighs not only the research results but also whether the method that produced them is sound.
- Checking whether the study design is appropriate, whether the sample is large enough, and whether the sample is free of bias
- Checking whether the measurement approach and the statistical conclusions have problems
- Reviewing whether the conclusions overstate the actual evidence and whether other interpretations are possible

**4. Coding that carries out several development steps on its own.** It does not stop at producing a line or two of code; it understands the goal and carries out several development tasks in sequence.
- Analyzing an existing codebase and tracing the cause of errors
- Modifying code across several files, implementing features, and writing tests
- Improving code structure and deciding the next task on its own during development

### When to choose Opus

- When the problem is specialized and difficult but **its scope is relatively clear**
- When in-depth logical analysis and review are needed
- When a technical document or paper must be understood precisely
- When you must find the gaps in a piece of research or analysis
- When you must solve complex coding or technical problems

## 3. Sonnet

**Main role:** A balanced general-purpose model that performs most everyday work reliably. Unless the work is very complex or needs specialized judgment, it can be used across writing, coding, research, and analysis.

### Work it suits

**1. Writing and content production.** It suits emails, blog posts, report drafts, ad copy, proofreading and rewriting sentences, presentation scripts, planning social media content, and brainstorming.

**2. General coding work.** It suits writing functions, fixing code errors, developing simple programs, explaining existing code, refactoring, writing test code, and producing data-processing scripts.

**3. Analysis and research.** It suits outlining a topic, comparing products and services, analyzing document content, simple competitor research, extracting key claims, comparing pros and cons, and organizing analysis results into tables or reports.

**4. Multi-step problem solving.** It breaks work with a clear scope into several steps and carries them out. Examples are summarizing material and then writing a speech, analyzing requirements and then producing code examples, or analyzing data and then explaining the results. Distinguish this from the long-running, autonomous projects you entrust to Fable.

**5. Repetitive and operational work.** It suits log parsing, format conversion, static file checks, running deploy scripts, and simple collection.

### When to choose Sonnet

- Use it when you are not sure which model to choose. When the call is hard to make, make sonnet the default.
- Use it when everyday work must be handled quickly and reliably.
- Use it when you perform several kinds of work together, such as writing, coding, and research.
- Use it when you are dealing with problems that are neither too simple nor overly complex.
- Use it when both speed and result quality must be considered.

## Criteria for telling Fable and Opus apart

- **Fable:** plans the whole job and carries it out autonomously for a long time.
- **Opus:** reasons deeply about and analyzes a complex problem whose scope is defined.

For example, **Opus** suits a deep critique of a single paper, while **Fable** suits reviewing dozens of papers, setting a research strategy, and producing the final report. Use Fable when the result of an earlier step affects the next step and the model must carry on through several steps by itself. Use Opus when you need to analyze one problem with a clear scope in depth.

## Rules for applying this in the harness

1. **Decide by the work.** Do not choose a model because "it is an important agent." Choose the model by weighing the complexity, expected duration, required autonomy, and response speed of the work the agent will take on.
2. **Do not assign the same model to everything without a reason.** Setting every agent to fable or opus only raises cost. Choose the suitable model for each agent and leave the reason as a comment.
3. **Separate the orchestration layer from the execution layer.** Even if you used fable for the layer that plans and coordinates (the main session or a supervisor agent), assign the worker agents beneath it models suited to each of their tasks. A fable orchestrator does not mean the worker agents need to be fable.
4. **Choose the model for each workflow stage.** In a `Workflow` script, you can assign a different model to each stage with `opts.model`. Use sonnet for repetitive collection and conversion stages, opus for in-depth verification, judging, and design stages, and fable for stages that make an overall plan and run for a long time.
