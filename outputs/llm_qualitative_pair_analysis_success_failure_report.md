# LLM Qualitative Pair Analysis

## 734d6579-c07d-47a8-9ae2-13339795476b

- Domain: `gimp`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this mixed success/failure pair, both evaluated models accurately described the procedural steps of each trajectory but failed to flag the unsuccessful trajectory's outcome or explain why the Colorize approach (doubao) failed while the Bucket Fill approach (UI-TARS) succeeded—demonstrating that current summarizers can faithfully narrate actions without capturing the critical distinction between effective and ineffective strategies.

### Trajectory contrast

The doubao agent (failed) used the Colorize dialog with Hue=120 and Saturation=1.0 to colorize the background layer, while the UI-TARS agent (succeeded) struggled extensively with the foreground color picker, eventually switched to HSV mode, set H=120/S=100/V=100, and used the Bucket Fill tool to fill the background with green. The doubao approach colorized existing pixel values rather than filling with a flat green, which likely caused the task failure.

The doubao agent's use of Colorize (which shifts hue/saturation of existing pixels) rather than a flat fill with green color explains its failure—Colorize modifies existing pixel colors rather than replacing them with a uniform green. The UI-TARS agent's approach of setting a foreground color and using Bucket Fill correctly replaced the background with green, despite extensive trial-and-error.

### Main qualitative findings

- **Finding:** Both models fail to flag the doubao trajectory as unsuccessful, presenting a failed approach as if it were valid.
  - Evidence: The doubao trajectory has success_binary=False, yet both model summaries describe the Colorize workflow without any indication that it did not achieve the task goal. Claude's summary even states 'colorizing the background layer with green' as if it succeeded.
  - Importance: For trajectory summarization to be useful for learning from agent behavior, summaries must distinguish between successful and unsuccessful approaches. Omitting failure status makes it impossible to learn what went wrong.
- **Finding:** The procedural difference that determines success vs. failure (Colorize vs. Bucket Fill) is accurately captured in the action descriptions but not interpreted as meaningful.
  - Evidence: Both models correctly describe Colorize for doubao and Bucket Fill for UI-TARS, but neither explains that Colorize modifies existing pixel hues while Bucket Fill replaces pixels with a flat color, which is the root cause of the outcome difference.
  - Importance: Summarizers that capture actions without interpreting their consequences may produce summaries that look correct but miss the most important lesson from paired trajectories.
- **Finding:** Claude provides more detailed struggle narratives but introduces temporal ordering errors; GPT-5.5 is more concise and factually precise but loses some procedural specificity.
  - Evidence: Claude's UI-TARS summary received temporal order 3/5 due to misplacing the black fill attempt, while GPT-5.5 received 4/5. However, Claude achieved 5/5 coverage vs. GPT-5.5's 4/5, and Claude captured the specific Ctrl+A + paste input method that GPT-5.5 omitted.
  - Importance: This illustrates a detail-accuracy tradeoff: more detailed summaries risk temporal errors, while more concise summaries risk omitting procedurally important details.
- **Finding:** GPT-5.5 correctly identified the paste input method for the doubao trajectory while Claude described it as typing.
  - Evidence: GPT-5.5's doubao summary says 'pasted 120' and 'pasted 1.0', matching the actual pyperclip.copy + ctrl+v method. Claude's summary says 'typed 120' and 'typed 1.0'.
  - Importance: Input method accuracy matters for reproducing agent behavior, especially when distinguishing between keyboard input and clipboard operations.

## 58565672-7bfe-48ab-b828-db349231de6b

- Domain: `multi_apps`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this mixed success/failure pair, both evaluated models produced procedurally accurate summaries but neither explicitly flagged the failing trajectory's unsuccessful outcome, with Claude Sonnet even adding speculative details that made the failure appear more intentional. This case illustrates a systematic gap in trajectory summarization: models faithfully describe what agents did but fail to capture whether the task was actually accomplished, undermining the utility of summaries for comparative agent analysis.

### Trajectory contrast

Both trajectories attempt the same task (open the first link in the latest email in the Bills folder in a new Chrome tab), but they operate on different email environments. The successful trajectory (doubao) identifies the latest email as an AWS invoice and clicks the 'Billing & Cost Management Page' link, which opens in Chrome. The failing trajectory (UI-TARS) identifies a different email ('Your receipt from X (formerly Twitter)') as the latest, right-clicks a Twitter help link and selects 'Open Link In Browser' from the context menu, but the task ultimately fails (success=0.0).

The failure of UI-TARS may relate to the link not actually opening in a new Chrome tab as required, or the wrong email being selected as 'latest' despite both appearing to have the same date. The successful trajectory used a direct click which triggered the default browser behavior, while the failing trajectory used a right-click context menu approach. The task required displaying in a 'new Chrome tab' specifically, and the right-click 'Open Link In Browser' approach may not have achieved this.

### Main qualitative findings

- **Finding:** Both models fail to explicitly identify task failure in the UI-TARS trajectory, presenting it as a completed sequence of reasonable actions.
  - Evidence: The UI-TARS trajectory has success_raw=0.0, yet Claude's summary states the agent 'proceeded with this action to open the link' and GPT-5.5 only notes the Chrome tab wasn't shown. Neither summary flags the task as unsuccessful.
  - Importance: For trajectory summarization to be useful for debugging or analysis, summaries must preserve outcome information. Smoothing over failure makes it impossible to distinguish successful from unsuccessful trajectories based on summaries alone.
- **Finding:** Claude Sonnet introduces minor hallucinations that inflate the apparent competence of the agent.
  - Evidence: Claude states the agent 'opened the Thunderbird email client' (it was already open) and 'determined that Chrome was likely the default browser' (speculative reasoning not clearly in the trajectory). The judge flagged the first as a minor hallucination.
  - Importance: Hallucinations that make agents appear more deliberate or capable than they were can mislead downstream analysis, especially when comparing successful and failing agents.
- **Finding:** Despite different outcomes, both models produce similarly high-scoring summaries for both trajectories, suggesting current evaluation may not adequately penalize failure omission.
  - Evidence: Both models receive Coverage 5, Temporal Order 5, and Procedural Usefulness 5 for both trajectories. The failing trajectory summaries score just as well as the successful ones, despite missing the critical failure signal.
  - Importance: This suggests that current evaluation criteria may be biased toward procedural accuracy over outcome accuracy, which is a significant gap for trajectory summarization evaluation.
- **Finding:** The procedural difference between direct click (successful) and right-click context menu (failed) is well-preserved by both models.
  - Evidence: Both models correctly describe the direct click on 'Billing & Cost Management Page' for the successful trajectory and the right-click 'Open Link In Browser' context menu approach for the failing trajectory.
  - Importance: Preserving method-level differences is important for understanding why one approach succeeded and another failed, even if the models don't explicitly connect method to outcome.

## da52d699-e8d2-4dc5-9191-a2199e0b6a9b

- Domain: `multi_apps`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this mixed success/failure pair, both evaluated models accurately described the procedural steps and preserved the different answers produced by each agent, but neither flagged the failing agent's critical omission of not visiting the required reference website—a key failure cause explicitly noted in the human gold summary. This illustrates a systematic gap: current summarization models capture what agents did but struggle to identify what agents failed to do, making it difficult for readers to understand why a trajectory resulted in failure.

### Trajectory contrast

Both agents attempted to identify the book with the slowest reading pace from a spreadsheet and write the result to a document. The failing agent (doubao) never visited the required reference website howlongtoread.com and simply read a pre-computed column value, identifying 'The Shining' as the answer. The successful agent (UI-TARS) performed mental calculations dividing word count by days to correctly identify 'Out of the Silent Planet', though it also did not explicitly visit the website. The agents arrived at different answers, with only the UI-TARS agent producing the correct one.

The doubao agent failed because it relied on a raw column value rather than computing words per day correctly, arriving at the wrong book ('The Shining'). The UI-TARS agent succeeded by performing the correct calculation and identifying 'Out of the Silent Planet'. The doubao agent also exhibited inefficient behavior (opening and closing files multiple times) and never consulted the reference website.

### Main qualitative findings

- **Finding:** Both evaluated models fail to note the doubao agent's omission of visiting the required reference website, a critical procedural gap that explains the task failure.
  - Evidence: The human gold summary explicitly states 'The agent never navigates to the website mentioned in the prompt.' Neither GPT-5.5 nor Claude mentions this. The judge flagged this as a minor omission for GPT-5.5 but noted 'neither candidate mentions this.'
  - Importance: For trajectory summarization, identifying deviations from task requirements is essential for understanding failure causes. Summaries that only describe what happened without noting what was skipped can obscure the reasons for failure.
- **Finding:** Claude provides more specific numerical details that enable verification of agent reasoning, particularly for the successful trajectory.
  - Evidence: Claude includes '47,840 words / 36.13 days ≈ 1,324 words/day' for the UI-TARS trajectory. GPT-5.5 only says the agent 'reasoned through the word counts and reading durations to compute words per day.' The judge noted this as a minor loss of specificity for GPT-5.5.
  - Importance: In mixed success/failure pairs, specificity about the reasoning process is crucial because it allows readers to understand why one approach succeeded and another failed. The numerical details make the correct methodology concrete.
- **Finding:** Both models accurately preserve the different answers produced by the two agents ('The Shining' vs. 'Out of the Silent Planet'), maintaining the factual contrast between trajectories.
  - Evidence: Both models received Factuality scores of 5 across both trajectories, and both correctly report the different book titles written to the document.
  - Importance: Preserving the concrete outputs is necessary for understanding the success/failure contrast, and both models do this well despite other omissions.
- **Finding:** Error-recovery sequences (accidental typing, failed paste attempts, undo operations) are well-preserved by both models, suggesting that observable UI errors are easier to summarize than reasoning-level failures.
  - Evidence: Both models capture the UI-TARS agent's accidental 'dd' typing, Ctrl+Z undo, and failed paste attempt. However, neither captures the doubao agent's reasoning-level error of using the wrong methodology to identify the slowest reading pace.
  - Importance: This asymmetry suggests that trajectory summarizers are better at capturing visible procedural errors than invisible reasoning failures, which has implications for how failure analysis should be approached in summarization.

## 7b1e1ff9-bb85-49be-b01d-d6424be18cd0

- Domain: `thunderbird`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

Even when summarizers accurately capture procedural errors and missteps in a failing trajectory, they may still present the outcome as successful if the agent's final actions superficially resemble task completion—highlighting a critical gap where trajectory summaries preserve process but lose outcome information, particularly in cases where failure is subtle rather than catastrophic.

### Trajectory contrast

Both agents follow a similar path (hamburger menu → Tools → Help → Troubleshooting Information → about:profiles), but the failing agent (doubao) makes an additional mistake by clicking 'Open Directory' which opens a file manager, requires closing it, and then clicks the about:profiles link three times redundantly. The successful agent (UI-TARS) navigates more efficiently in 8 steps without the file manager detour.

The doubao agent's failure (score 0.0) despite eventually reaching about:profiles is puzzling—it may be that the repeated clicking or the file manager detour left the environment in an unexpected state, or the evaluation criteria were not met despite apparent task completion. The UI-TARS agent completed the task cleanly in fewer steps with a success score of 1.0.

### Main qualitative findings

- **Finding:** Both models describe procedural errors without connecting them to task failure outcomes.
  - Evidence: The doubao trajectory has success_raw=0.0, yet Claude's summary says the agent 'considered the task complete' and GPT-5.5 says it 'issued DONE and terminated'—neither flags that the task actually failed.
  - Importance: For trajectory summarization to be useful for debugging or analysis, summaries should distinguish between agents that completed a task and agents that merely terminated. Describing errors without noting failure can mislead downstream consumers.
- **Finding:** Claude Sonnet 4.6 provides more granular procedural detail than GPT-5.5, particularly for the failing trajectory.
  - Evidence: Claude includes step number references (e.g., 'steps 12–14'), exact click counts ('multiple times'), and mentions waiting steps. GPT-5.5 uses vaguer language ('clicked the about:profiles link repeatedly'). This is reflected in Claude receiving Specificity=5 vs GPT-5.5's Specificity=4 for the doubao summary.
  - Importance: Higher specificity in error-containing trajectories is valuable for understanding what went wrong and for procedural reconstruction.
- **Finding:** Both models produce highly similar summaries for the successful trajectory, with only minor specificity differences.
  - Evidence: Both received Coverage=5, Factuality=5, Temporal order=5 for the UI-TARS trajectory. The only difference was Claude mentioning the hamburger menu location (top-right corner), earning Specificity=5 vs GPT-5.5's Specificity=4.
  - Importance: Successful, straightforward trajectories are easier to summarize accurately, and model differences emerge more clearly on error-containing or failing trajectories.
- **Finding:** The paired case reveals that task failure can be opaque even to high-quality summarizers when the agent's final actions superficially resemble success.
  - Evidence: The doubao agent reached the about:profiles page and issued DONE, yet scored 0.0. Neither model's summary provides any indication that the task was not successfully completed. The repeated clicking (3 times) may have caused an issue, but this is not analyzed by either model.
  - Importance: This highlights a limitation of trajectory summarization: without access to evaluation results or environmental state verification, summarizers may not be able to distinguish apparent completion from actual failure.

## 847a96b6-df94-4927-97e6-8cc9ea66ced7

- Domain: `vs_code`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

This mixed-outcome pair demonstrates that both evaluated models reliably preserve the critical behavioral difference between a stuck agent (90+ repeated identical actions) and one that adapts its strategy, correctly representing failure in both cases. Claude Sonnet 4.6 provides notably more procedural specificity (step ranges, coordinates, attempt counts) that aids failure diagnosis, while GPT-5.5 captures the same narrative arc more concisely—illustrating a specificity-conciseness tradeoff in trajectory summarization.

### Trajectory contrast

Both agents successfully open the first workspace and then get stuck repeatedly clicking the File menu when trying to open the second. The doubao agent (100 steps, failure) remains stuck in the File menu clicking loop for ~90 steps without recovery. The UI-TARS agent (16 steps, success) also gets stuck but recovers by switching to the Command Palette via Ctrl+Shift+P, then issues a FAIL action—yet is marked as task-successful (success_raw=1.0), suggesting the task was actually completed despite the agent's self-reported failure.

The success/failure labels are somewhat paradoxical: the UI-TARS trajectory is marked successful despite the agent issuing a FAIL action and never visibly opening workspace2 in the trajectory. This may indicate the Command Palette action or some post-trajectory state resolved the task. The doubao trajectory is a clear failure—stuck in an infinite loop with no recovery strategy. The key behavioral difference is that UI-TARS adapted its strategy (Command Palette) while doubao did not.

### Main qualitative findings

- **Finding:** Both models accurately preserve the critical strategic difference between trajectories: one agent adapts (Command Palette) while the other persists in a failing loop.
  - Evidence: Both GPT-5.5 and Claude summaries for UI-TARS mention the Ctrl+Shift+P Command Palette switch; both doubao summaries describe the persistent File menu clicking loop without recovery.
  - Importance: This strategic adaptation is the key behavioral difference that likely explains divergent task outcomes, making it essential for trajectory summarization to preserve.
- **Finding:** Claude Sonnet 4.6 consistently provides more procedural specificity (step numbers, coordinates, attempt counts) without sacrificing accuracy, earning higher specificity scores.
  - Evidence: Claude received Specificity 5/5 for both trajectories; GPT-5.5 received 3/5 (doubao) and 4/5 (UI-TARS). Judge errors for GPT-5.5 cite missing step numbers, coordinates, and attempt counts.
  - Importance: For failure analysis and debugging, specific procedural details help reconstruct agent behavior and identify root causes of failure loops.
- **Finding:** Neither model addresses the paradoxical success label of the UI-TARS trajectory, where the agent issues FAIL but the task is marked successful.
  - Evidence: Both models' UI-TARS summaries conclude the task was not completed, consistent with the trajectory evidence but inconsistent with the success_raw=1.0 metadata.
  - Importance: This highlights a limitation of trajectory summarization: models summarize observable behavior faithfully but cannot reconcile it with external evaluation signals, which may matter for meta-analysis of agent performance.
- **Finding:** The doubao trajectory's extreme repetition (90+ identical clicks) is a stress test for summarization conciseness, and both models handle it well by abstracting the loop rather than enumerating steps.
  - Evidence: GPT-5.5 describes 'dozens of times'; Claude specifies '~90 repeated click attempts across Steps 9–100 with slight coordinate variations.' Both avoid step-by-step enumeration.
  - Importance: Summarizing repetitive failure loops concisely while preserving their extent is a key challenge for trajectory summarization; this case shows both models handle it effectively with different levels of precision.

## e2b5e914-ffe1-44d2-8e92-58f8c5d92bb2

- Domain: `vs_code`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

This paired case reveals that both evaluated models struggle to explicitly communicate task failure when the agent's final actions appear superficially correct, and that summarization quality diverges most on error-recovery sequences—Claude Sonnet 4.6 preserved specific procedural details of the failed trajectory (dropdown interactions, value concatenation error, Ctrl+A recovery) while GPT-5.5 used vague abstractions, suggesting that complex, error-prone trajectories are the most discriminating test cases for summarization fidelity.

### Trajectory contrast

Both agents attempted to disable Python missing import error reporting in VS Code settings. The failed agent (doubao) took 14 steps, encountered errors during value entry (e.g., 'warningnone' concatenation), and had to recover by selecting all text and overwriting with correct JSON. The successful agent (UI-TARS) completed the task cleanly in 8 steps with no errors, using a more direct search query and straightforward editing.

The failed agent's longer trajectory reflects procedural missteps: it searched generically for 'python', used autocomplete/dropdown interactions that led to malformed values, and had to perform a full overwrite to correct the file. Despite the final content appearing correct, the task was marked as failed (possibly due to overwriting all settings rather than adding to existing ones, or a file-save issue). The successful agent searched directly for the specific setting key, made a clean edit, and explicitly saved.

### Main qualitative findings

- **Finding:** The missing Ctrl+S save step in the failed trajectory was not highlighted by either model as a potential cause of failure.
  - Evidence: The successful trajectory's gold summary and both model summaries mention saving with Ctrl+S. The failed trajectory's gold summary and model summaries do not mention saving. Neither model flagged this omission as potentially significant.
  - Importance: For trajectory summarization, identifying the absence of critical steps (like saving) is essential for understanding why a task failed, especially when the content appears correct.
- **Finding:** Claude Sonnet 4.6 maintained higher specificity than GPT-5.5 on the error-prone (failed) trajectory while both performed equally well on the clean (successful) trajectory.
  - Evidence: Claude received 5/5 on specificity for the failed trajectory while GPT received 3/5. The judge flagged GPT's vague language ('interacted with', 'opened/used') and missing Ctrl+A detail as minor issues.
  - Importance: Summarizing error-recovery sequences requires more granular detail than summarizing clean workflows. Models that default to vague language lose important procedural information precisely when it matters most.
- **Finding:** Both models produced near-identical quality summaries for the straightforward successful trajectory but diverged on the more complex failed trajectory.
  - Evidence: Both models received perfect 5/5 scores across all dimensions for the successful trajectory. For the failed trajectory, Claude received all 5s while GPT received 3-4 on specificity and procedural usefulness.
  - Importance: This suggests that trajectory complexity and error-handling sequences are a discriminating factor for summarization quality, making mixed-outcome pairs valuable test cases.
- **Finding:** Neither model explicitly labeled the trajectory outcome as success or failure, potentially misleading downstream consumers.
  - Evidence: Claude's failed trajectory summary concludes with 'the correct configuration setting reportMissingImports to none', implying success. GPT's summary does not state the outcome. The task was marked as failed (success_raw: 0.0).
  - Importance: Trajectory summaries that do not clearly communicate task outcomes can mislead users about agent capabilities, especially when the final state appears superficially correct.

## b4f95342-463e-4179-8c3f-193cd7241fb2

- Domain: `chrome`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

This paired case reveals a boundary condition for mixed success/failure analysis: when two trajectories are behaviorally identical but carry different success labels (likely due to environment-level factors rather than agent actions), both evaluated models appropriately describe the observable behavior without fabricating distinctions, demonstrating that good summarizers are robust to misleading metadata. However, the case has limited value for studying failure-awareness since there is no observable behavioral difference to preserve.

### Trajectory contrast

Both trajectories follow nearly identical procedural steps: search for 'Diamond' on Recreation.gov, click the DIAMOND campground result, scroll down, click 'Next Available', encounter an error popup, click 'Refresh', then wait for the remaining ~90 steps. The doubao agent is marked as failure (0.0) while the UI-TARS agent is marked as success (1.0), despite both exhibiting the same observable behavior and neither visibly retrieving next available dates.

The success/failure distinction appears to be based on evaluation criteria not directly observable in the trajectory behavior itself. Both agents performed the same actions and ended in the same apparent state (waiting after a refresh). The success label for UI-TARS may reflect that the task was considered complete once the 'Next Available' button was clicked and the refresh was attempted, or that the evaluation environment eventually loaded the result. The failure label for doubao is puzzling given identical behavior, suggesting the evaluation may depend on timing or backend state rather than agent actions.

### Main qualitative findings

- **Finding:** Behaviorally identical trajectories can have different success labels, creating a challenge for summarization evaluation.
  - Evidence: Both trajectories follow the exact same steps (search → click → scroll → Next Available → error → Refresh → wait), yet doubao is labeled failure (0.0) and UI-TARS is labeled success (1.0). Both human gold summaries describe essentially the same sequence. Both model summaries for both trajectories describe the same outcome (no dates retrieved).
  - Importance: This case illustrates that trajectory summarization quality cannot always be evaluated against success/failure labels when the observable behavior is identical. Summarizers should describe what happened rather than infer outcomes from labels.
- **Finding:** Both evaluated models produce highly consistent summaries across behaviorally equivalent trajectories.
  - Evidence: Claude and GPT-5.5 both received Coverage 5, Factuality 5, Temporal order 5, and Procedural usefulness 5 for both trajectories. The summaries are structurally and substantively very similar across the paired cases.
  - Importance: This demonstrates that when trajectories are procedurally identical, good summarizers produce consistent descriptions regardless of the source agent, which is a desirable property.
- **Finding:** Claude provides slightly higher specificity than GPT-5.5, particularly in noting step ranges and terminal conditions.
  - Evidence: Claude received Specificity 5 for both trajectories while GPT-5.5 received Specificity 4 for both. The judge noted GPT-5.5's omission of the step range for WAIT actions. Claude also explicitly noted the absence of a DONE action in the doubao summary.
  - Importance: For trajectory summarization, specificity about the scale of repetitive actions (like 90 consecutive WAITs) helps readers understand agent behavior patterns and potential issues.
- **Finding:** This case has limited utility for studying failure-awareness in summarization because the 'failure' trajectory is behaviorally indistinguishable from the 'success' trajectory.
  - Evidence: The human gold summaries for both trajectories describe the same sequence. The success/failure distinction appears to be an artifact of evaluation timing or environment state rather than agent behavior.
  - Importance: Cases where success/failure labels diverge without behavioral differences are poor candidates for evaluating whether summarizers preserve failure information, since there is no behavioral failure to preserve.

## 8979838c-54a5-4454-a2b8-3d135a1a5c8f

- Domain: `libreoffice_impress`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

In this mixed success/failure LibreOffice Impress case, both GPT-5.5 and Claude Sonnet correctly identified the failing agent's premature termination (copying title text but never pasting it into notes) and preserved error-recovery details in the successful trajectory, demonstrating that current models can reliably distinguish complete from incomplete task execution in trajectory summaries. However, the uniformly high judge scores across both models limit this case's ability to discriminate between summarizer quality, while the divergence between automatic metrics and judge ratings underscores the limitations of surface-level evaluation for this task.

### Trajectory contrast

Both agents successfully changed the slide background to purple using the Properties panel. The failing agent (doubao) copied the title text but issued DONE without pasting it into the notes section. The successful agent (UI-TARS) completed the full workflow: it made a drag-selection mistake, undid it, correctly copied the title, navigated through Insert then View menus to find the Notes pane, pasted the title, and saved the file.

The doubao agent failed because it stopped after copying the title text without ever navigating to or pasting into the notes area. The UI-TARS agent succeeded despite making two notable errors (accidental text box move and looking in the wrong menu first) because it recovered from both and completed all required steps.

### Main qualitative findings

- **Finding:** Both evaluated models successfully preserved the critical success/failure distinction between paired trajectories.
  - Evidence: Both models explicitly noted the premature DONE in the failing trajectory and the complete paste-and-save workflow in the successful trajectory. All judge scores for coverage, factuality, and procedural usefulness were 5/5 across all four summaries.
  - Importance: This demonstrates that modern LLMs can reliably detect and report incomplete task execution, which is essential for trajectory summarization to be useful for debugging and analysis.
- **Finding:** Both models captured error-recovery patterns in the successful trajectory, preserving important procedural learning signals.
  - Evidence: Both models described the accidental text box move, the Ctrl+Z undo, and the incorrect Insert menu exploration before finding View > Notes. These details were present in both the GPT-5.5 and Claude summaries of the UI-TARS trajectory.
  - Importance: Error-recovery sequences are valuable for understanding agent behavior and improving future agents. Summarizers that preserve these patterns provide more actionable summaries than those that only report the final successful path.
- **Finding:** This case represents a ceiling performance scenario where both models achieve near-perfect scores, limiting its discriminative value.
  - Evidence: All eight judge dimension scores across both models and both trajectories are 5/5 (with one exception of 4/5 for GPT-5.5 specificity on the successful trajectory). No errors were flagged by the judge for any summary.
  - Importance: While this validates that trajectory summarization works well for relatively straightforward LibreOffice tasks, it suggests the case may be less useful for highlighting model differences than cases with more complex or ambiguous trajectories.
- **Finding:** Automatic metrics (ROUGE-L, BERTScore) show notable variation despite uniformly high judge scores, suggesting these metrics may not reliably capture summary quality for this task.
  - Evidence: ROUGE-L ranges from 0.35 to 0.51 and BERTScore from 0.29 to 0.50 across the four summaries, yet all receive perfect or near-perfect judge scores. GPT-5.5 consistently scores higher on automatic metrics than Claude despite equivalent judge ratings.
  - Importance: This highlights a potential disconnect between surface-level text overlap metrics and actual summary quality as assessed by judges, which is relevant for the paper's methodology discussion.

## 936321ce-5236-426a-9a20-e0e3c5dc536f

- Domain: `libreoffice_writer`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

In this mixed success/failure pair, both GPT-5.5 and Claude Sonnet 4.6 achieved perfect judge scores across all dimensions, correctly preserving the self-correction loop in the successful trajectory and the premature termination in the failed one. This case demonstrates that current models can reliably distinguish and communicate different failure modes, though the divergence between perfect judge scores and variable reference-based metrics (ROUGE-L ranging from 0.42 to 0.53) suggests that automatic metrics may underestimate summary quality for trajectory summarization tasks.

### Trajectory contrast

The successful trajectory (doubao) initially failed to open the Text to Table dialog because no text was selected, then corrected by selecting text first and re-navigating the menu. The failed trajectory (UI-TARS) correctly selected text first and opened the dialog with proper settings, but terminated with FAIL before clicking OK to confirm the conversion.

The successful agent overcame an initial procedural error (not selecting text) through self-correction, while the failed agent followed the correct procedure but stopped prematurely before the final confirmation step. The failure is not due to a wrong approach but to incomplete execution.

### Main qualitative findings

- **Finding:** Both evaluated models achieved perfect judge scores (5/5 across all dimensions) for both trajectories in this pair, demonstrating that modern LLMs can reliably summarize both successful and failed trajectories.
  - Evidence: All four summaries received Coverage: 5, Factuality: 5, Temporal order: 5, Specificity: 5, Procedural usefulness: 5, with no omissions or hallucinations flagged.
  - Importance: This suggests that for relatively straightforward GUI tasks with clear action sequences, current models can produce high-quality summaries regardless of trajectory outcome.
- **Finding:** Both models correctly preserved the critical distinction between a self-correcting successful trajectory and a procedurally correct but prematurely terminated failed trajectory.
  - Evidence: For the success case, both models describe the initial failed attempts and the correction of selecting text first. For the failure case, both explicitly mention the FAIL action and the missing OK confirmation.
  - Importance: Preserving the nature and cause of failure is essential for trajectory summarization to be useful for debugging and agent improvement. This case shows models can distinguish between different failure modes.
- **Finding:** Despite identical perfect judge scores, reference-based metrics (ROUGE-L, BERTScore) show meaningful variation across models, suggesting these automatic metrics may not align well with human quality judgments for this task.
  - Evidence: GPT-5.5 achieved ROUGE-L of 0.533 vs Claude's 0.419 on the success trajectory, yet both received identical judge scores. Similarly, on the failure trajectory, scores diverged (GPT: 0.519 ROUGE-L vs Claude: 0.434) with identical judge ratings.
  - Importance: This highlights a potential limitation of reference-based metrics for evaluating trajectory summaries, where multiple valid phrasings can capture the same essential information.
- **Finding:** The failed trajectory was simpler (8 steps) and followed a more linear procedure than the successful one (17 steps with self-correction), yet both models handled the complexity difference well.
  - Evidence: The successful trajectory required summarizing a failed attempt, a correction, and a successful reattempt, while the failed trajectory was a straightforward sequence ending in premature termination. Both models structured their summaries appropriately for each complexity level.
  - Importance: This demonstrates that summarization models can adapt their output structure to trajectory complexity, which is important for handling diverse agent behaviors.

## c2751594-0cd5-4088-be1b-b5f2f9ec97c4

- Domain: `multi_apps`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

Both evaluated models correctly preserved the critical success/failure distinction in this mixed-outcome pair, accurately reporting the FAIL terminal action in the unsuccessful trajectory and DONE in the successful one. However, GPT-5.5 showed a slight advantage in capturing mid-trajectory failures (repeated minimize attempts), which Claude smoothed over—suggesting that even when terminal outcomes are correctly reported, procedural struggle details may be lost in summarization.

### Trajectory contrast

Both agents followed nearly identical procedures: finding the email in the Notes folder, saving the attachment, extracting the first image from the document, and attempting to set it as the desktop background. The doubao agent saved the file to Desktop and opened it from there, while UI-TARS opened it directly from Thunderbird via LibreOffice Writer. UI-TARS saved the image to the Pictures folder as 'bg_image.png', while doubao saved it to the Desktop as 'exported_image.png'. UI-TARS had trouble minimizing LibreOffice (three failed attempts) but ultimately succeeded. The doubao agent completed all apparent steps but terminated with FAIL, while UI-TARS terminated with DONE and achieved success.

The doubao agent performed all the right steps but issued a FAIL action at the end, possibly due to the background not actually being applied (perhaps the image was not properly selected/confirmed in the background settings). UI-TARS succeeded despite encountering minimize failures mid-trajectory, suggesting the final confirmation step was executed correctly.

### Main qualitative findings

- **Finding:** Both models correctly preserve terminal failure status (FAIL vs DONE) across paired trajectories.
  - Evidence: GPT-5.5 states 'The trajectory ended with a FAIL status rather than DONE' for doubao; Claude states 'the agent issued a FAIL action, indicating the task was not successfully completed.' Both correctly report DONE for UI-TARS.
  - Importance: Terminal action status is the most critical signal distinguishing success from failure in agent trajectories. Correct preservation ensures downstream analysis can differentiate outcomes.
- **Finding:** GPT-5.5 better preserves mid-trajectory failures and recovery behaviors compared to Claude.
  - Evidence: GPT-5.5 notes 'attempted several times to minimize LibreOffice Writer, eventually closed it' for UI-TARS, while Claude omits the minimize failures entirely. The judge flagged this as a minor omission for Claude (Coverage 4 vs 5).
  - Importance: Mid-trajectory failures and workarounds reveal agent robustness and problem-solving strategies. Omitting them loses information about agent behavior patterns.
- **Finding:** Both models achieve high factuality and avoid hallucination across both success and failure trajectories.
  - Evidence: All four summaries received Factuality scores of 4-5 and no hallucination severity flags from the judge.
  - Importance: Demonstrates that current models can summarize agent trajectories without fabricating details, even when the trajectory outcome is ambiguous (doubao completed all steps but reported FAIL).
- **Finding:** The doubao trajectory presents an interesting case where all procedural steps appear correct but the agent self-reports failure, and both models handle this ambiguity appropriately.
  - Evidence: GPT-5.5 hedges with 'apparently attempting to apply it' and 'successful completion was not confirmed.' Claude directly states the FAIL action. Neither model fabricates an explanation for why the task failed.
  - Importance: Summarizers should report what happened without over-interpreting ambiguous outcomes. Both models demonstrate appropriate restraint.
