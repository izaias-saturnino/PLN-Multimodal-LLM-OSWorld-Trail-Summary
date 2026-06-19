# LLM Qualitative Pair Analysis

## 045bf3ff-9077-4b86-b483-a1040a949cff

- Domain: `gimp`
- Pair outcome: `both_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

When two agents fail the same task via fundamentally different strategies (e.g., browsing for an ICC profile vs. changing image precision), both GPT-5.5 and Claude Sonnet 4.6 successfully preserve the distinct failure modes in their summaries, demonstrating that modern summarizers can differentiate failure types—not just success from failure. However, this case also starkly illustrates the unreliability of automatic metrics for trajectory summarization, with BERTScore as low as 0.107 for a summary that received perfect scores from human judges.

### Trajectory contrast

Both trajectories fail to convert the image to CMYK mode in GIMP, but they pursue fundamentally different strategies after discovering that CMYK is not available in the Mode submenu. The doubao agent attempts to find a CMYK ICC profile via Image > Color Management > Convert to Color Profile and browses the filesystem. The UI-TARS agent hypothesizes that changing image precision to 32-bit floating point might unlock a CMYK option in the Mode submenu, changes precision, then re-checks Mode and still fails.

Both agents fail (success_raw = 0.0). The failures stem from different misconceptions: the doubao agent's approach of finding a CMYK ICC profile was more technically sound but it couldn't locate an appropriate profile file. The UI-TARS agent's approach of changing precision was based on an incorrect hypothesis and predictably failed.

### Main qualitative findings

- **Finding:** Both summarization models successfully differentiate two distinct failure strategies for the same task.
  - Evidence: For doubao, both models describe the ICC profile filesystem browsing approach. For UI-TARS, both models describe the precision-change hypothesis. These are qualitatively different failure modes that are correctly preserved.
  - Importance: Trajectory summarization must preserve not just success/failure outcomes but the reasoning and strategy behind failures, as different failure modes carry different diagnostic value.
- **Finding:** Automatic metrics (ROUGE-L, BERTScore) diverge substantially from judge scores, especially for the UI-TARS trajectory.
  - Evidence: Claude's UI-TARS summary received perfect judge scores (5 across all dimensions, no errors) but a BERTScore of only 0.107 and ROUGE-L of 0.338. GPT's UI-TARS summary also received near-perfect judge scores but similarly low automatic metrics.
  - Importance: This case strongly illustrates that reference-based automatic metrics can be unreliable for evaluating trajectory summaries, particularly when the summary is accurate but uses different phrasing or structure than the reference.
- **Finding:** Both models consistently omit repeated-click behaviors that indicate navigation difficulties.
  - Evidence: Both models omit that the doubao agent clicked Mode twice and Color Management twice. For UI-TARS, Claude does mention 'multiple times' for Mode clicks. The judges rated these omissions as minor.
  - Importance: Repeated clicks may signal agent confusion or UI interaction difficulties. While judges consider these minor, systematic omission of such patterns could mask important information about agent reliability and interaction quality.
- **Finding:** Claude achieves slightly higher specificity than GPT across both trajectories in this pair.
  - Evidence: Claude received specificity scores of 5 for both trajectories; GPT received 4 for both. Claude includes details like 'visible files appeared to be RGB-type profiles' (doubao) and step-level references (UI-TARS).
  - Importance: Higher specificity in failure trajectories helps downstream analysis understand exactly where and why the agent's approach broke down.

## 734d6579-c07d-47a8-9ae2-13339795476b

- Domain: `gimp`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this mixed-success GIMP task, both GPT-5.5 and Claude Sonnet 4.6 produced detailed procedural summaries but neither flagged the failed trajectory's unsuccessful outcome, presenting the Colorize approach as if it achieved the goal. This demonstrates a critical blind spot in trajectory summarization: when a procedure appears reasonable but produces incorrect results, current models may smooth over failure, making it impossible for downstream users to distinguish effective from ineffective strategies.

### Trajectory contrast

The doubao agent (failed) used the Colorize dialog with Hue=120 and Saturation=1.0 to colorize the background layer, while the UI-TARS agent (succeeded) went through a lengthy struggle with the foreground color picker, eventually switching to HSV mode and using Bucket Fill to correctly fill the background with green.

The doubao agent's Colorize approach apparently did not produce the correct result (success=0.0), likely because Colorize modifies existing pixel colors rather than filling with a solid green. The UI-TARS agent's Bucket Fill approach, despite many failed attempts and a black fill mistake, ultimately succeeded by correctly setting HSV values and using the fill tool.

### Main qualitative findings

- **Finding:** Both models fail to flag the doubao trajectory's task failure, presenting an unsuccessful approach as if it succeeded.
  - Evidence: Doubao has success_raw=0.0, yet GPT-5.5 says it made 'the selected layer green' and Claude says it was 'colorizing the background layer with green.' Neither mentions the approach did not achieve the desired result.
  - Importance: For trajectory summarization, distinguishing successful from unsuccessful procedures is critical. If summaries of failed trajectories read identically to successful ones, downstream users cannot learn from failures or identify which methods work.
- **Finding:** Both models effectively capture the struggle and recovery narrative in the complex UI-TARS trajectory.
  - Evidence: Both summaries describe the multiple failed attempts, the black fill mistake, the HSV mode switch, and the eventual successful fill. Claude provides more specific input method details; GPT-5.5 provides a more fluid narrative.
  - Importance: Capturing trial-and-error processes is important for understanding agent behavior and debugging, and both models handle this well for the longer, more complex trajectory.
- **Finding:** Claude's temporal ordering error in the UI-TARS summary illustrates a challenge with summarizing long, non-linear trajectories.
  - Evidence: Claude placed the black fill description (step 8) after the HSV color setting steps (steps 5-6), but the black fill occurred before the HSV switch in the actual trajectory. The judge scored temporal order at 3.
  - Importance: Correct temporal ordering is essential for procedural summaries, especially when the sequence of events (failure → diagnosis → correction) is itself informative.
- **Finding:** GPT-5.5 more accurately described the input method for the doubao trajectory (paste vs. type), while Claude was more specific about the UI-TARS input method.
  - Evidence: GPT-5.5 correctly said 'pasted' for doubao; Claude said 'typed.' For UI-TARS, Claude specified 'Ctrl+A to select all, then pasted 100' while GPT-5.5 omitted this detail.
  - Importance: Input method specificity matters for reproducibility and understanding agent capabilities, and the models showed complementary strengths across the two trajectories.
- **Finding:** The procedural difference between Colorize and Bucket Fill — the core reason one trajectory failed and the other succeeded — is preserved in the summaries but not explicitly contrasted or evaluated.
  - Evidence: The doubao summaries describe Colorize; the UI-TARS summaries describe Bucket Fill. But without failure flagging, a reader would not understand why the method choice mattered.
  - Importance: Summarizers should ideally help users understand not just what happened but whether the approach was effective, especially when different methods lead to different outcomes.

## 1e8df695-bd1b-45b3-b557-e7d599cf7597

- Domain: `libreoffice_calc`
- Pair outcome: `both_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

When both trajectories in a pair fail but with divergent execution quality—one procedurally clean, the other visibly struggling—current summarization models describe procedures accurately but uniformly fail to flag task-level failure outcomes, potentially misleading users about agent effectiveness. Additionally, models may introduce asymmetric speculation, adding unwarranted doubt to clean trajectories while accurately describing troubled ones.

### Trajectory contrast

Both trajectories attempt the same task (adding a Profit column with formula =B2-C2 and filling down), but the doubao agent completes the process smoothly in 9 steps with a clean fill handle drag, while the UI-TARS agent struggles with multiple failed fill handle drag attempts over 14 steps, requiring undo operations and repeated retries before eventually filling most rows, then needing an additional drag for the last row.

Both are marked as failures (success_raw: 0.0), which is notable because the doubao trajectory appears procedurally clean while the UI-TARS trajectory has clear execution difficulties. The doubao failure may be due to an undetected issue with the fill handle drag (imprecise coordinates) or a file-saving issue, while the UI-TARS failure likely stems from incomplete or incorrect formula propagation despite multiple attempts.

### Main qualitative findings

- **Finding:** Both models fail to flag task-level failure outcomes even when both trajectories are marked as unsuccessful.
  - Evidence: Both trajectories have success_raw: 0.0, yet all four summaries describe the procedures as if they were completed successfully. No summary questions whether the final result was correct.
  - Importance: Trajectory summaries that omit task outcome information can mislead downstream users about agent reliability. This is especially problematic when a procedurally clean-looking trajectory actually fails.
- **Finding:** Claude Sonnet 4 applies speculative hedging asymmetrically—adding doubt to the clean trajectory while accurately describing the troubled one.
  - Evidence: For doubao (clean execution), Claude adds 'may or may not have precisely targeted the fill handle corner' (judged as misleading). For UI-TARS (troubled execution), Claude accurately describes multiple failures without unnecessary hedging.
  - Importance: This shows that model-generated uncertainty can be miscalibrated: speculation is added where evidence doesn't support it, while genuine execution problems are described factually. This asymmetry could distort comparative analysis of agent performance.
- **Finding:** GPT-5.5 better preserves the procedural contrast between the two trajectories without introducing artifacts.
  - Evidence: GPT-5.5 received perfect judge scores (5/5 across all dimensions, no errors) for the doubao summary and only minor specificity loss for UI-TARS. Claude received a minor misleading framing error for doubao but perfect scores for UI-TARS.
  - Importance: For paired trajectory analysis, maintaining accurate procedural descriptions without speculation is critical for preserving meaningful contrasts between agent behaviors.
- **Finding:** The both-failure pair with divergent execution quality reveals a blind spot in summarization: models describe procedures but not outcomes.
  - Evidence: The doubao trajectory looks procedurally successful (9 clean steps) while UI-TARS shows clear struggles (14 steps with multiple retries), yet both fail. Neither model's summaries help explain why the clean-looking trajectory failed.
  - Importance: This highlights the need for summarizers to incorporate outcome information or at least flag uncertainty about task completion, especially when procedural descriptions alone are insufficient to determine success.

## 4172ea6e-6b77-4edb-a9cc-c0014bd1603b

- Domain: `libreoffice_calc`
- Pair outcome: `both_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

This both-failure paired case reveals that Claude Sonnet 4 produces more specific and definitive failure descriptions—quantifying loop iterations and noting absent alternative strategies—while GPT-5.5 hedges on failure outcomes with vague language. Notably, Claude's superior judge scores (perfect 5s vs. 3-4 on specificity) inversely correlate with its lower automatic metric scores, demonstrating that ROUGE-L and BERTScore can penalize comprehensive, detailed summaries that diverge lexically from gold references.

### Trajectory contrast

Both trajectories fail to complete the task, but they fail in subtly different ways. The doubao agent gets stuck in a loop of clicking C2 and attempting to drag the fill handle without any visible effect, never trying an alternative approach. The UI-TARS agent also fails at the fill handle but its drag operations actively move cell contents rather than copying them, requiring repeated Ctrl+Z undos to restore the original formula before retrying.

Both agents fail (success=0.0) and both get stuck in repetitive loops for the majority of their 100 steps. The failure mode differs: doubao's drag simply doesn't work (no effect), while UI-TARS's drag incorrectly moves content, creating a more complex failure pattern involving undo operations.

### Main qualitative findings

- **Finding:** Claude consistently provides more specific quantitative details about failure loops than GPT-5.5.
  - Evidence: Claude mentions '~45 times' for doubao and '~80+ steps' for UI-TARS loops, while GPT-5.5 says 'many times' and 'repeatedly' without quantification. This is reflected in Claude receiving Specificity scores of 5 for both, vs. GPT-5.5 receiving 3 and 4.
  - Importance: Quantifying repetitive failure behavior is crucial for understanding agent limitations and the severity of stuck states. Vague descriptions understate the problem.
- **Finding:** Both models correctly preserve the distinct failure mechanisms between the two trajectories.
  - Evidence: For doubao, both note the drag had no effect. For UI-TARS, both note the drag moved content and required Ctrl+Z undos. This matches the gold summaries' descriptions.
  - Importance: Preserving mechanistic differences between failures is essential for diagnosing agent problems and comparing agent architectures.
- **Finding:** GPT-5.5 tends to hedge on failure outcomes rather than stating them definitively.
  - Evidence: For doubao, GPT-5.5 says 'no visible confirmation that the formulas were successfully filled' rather than clearly stating the task was incomplete. The judge flagged this as a minor loss of specificity.
  - Importance: Hedging language in failure descriptions can mislead readers about whether a task actually failed or whether the outcome is merely uncertain.
- **Finding:** Claude's higher judge scores do not correspond to higher automatic metrics, highlighting a disconnect between lexical overlap measures and content quality.
  - Evidence: Claude receives perfect 5s across all judge dimensions for both trajectories but has lower ROUGE-L (0.269/0.284) and BERTScore (0.231/0.243) than GPT-5.5 (0.363/0.358 and 0.370/0.337).
  - Importance: This demonstrates that automatic metrics like ROUGE-L and BERTScore may penalize more detailed, comprehensive summaries that use different vocabulary than gold references, making them unreliable as sole evaluation measures for trajectory summarization.

## 550ce7e7-747b-495f-b122-acdc4d0b8e54

- Domain: `libreoffice_impress`
- Pair outcome: `both_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this both-failure paired case, the two models show complementary strengths—Claude Sonnet 4.6 better preserves quantitative details about repetitive loops while GPT-5.5 better distinguishes procedurally distinct failure phases—but neither model flags that the task ultimately failed despite apparent completion, revealing a systematic blind spot in trajectory summarization when failure is not overtly signaled by the agent's actions.

### Trajectory contrast

Both trajectories attempt the same strikethrough task in LibreOffice Impress and both are marked as failures (success=0.0), but they differ in their specific failure modes and recovery strategies. The doubao agent gets stuck in a long undo loop (~15 consecutive undo clicks) without entering edit mode explicitly, while the UI-TARS agent makes the distinct mistake of moving the text box before learning to double-click into edit mode, then scrambles text within edit mode, and ultimately saves the file with Ctrl+S.

Both are scored as failures despite both agents eventually applying strikethrough to both lines. The failure likely stems from the formatting not being correctly applied or saved, or the text being left in a corrupted state. Both agents struggled significantly with text selection via drag operations.

### Main qualitative findings

- **Finding:** Models show complementary strengths across paired trajectories, with each excelling on one trajectory but underperforming on the other.
  - Evidence: Claude Sonnet 4.6 scores 5/5 on doubao but 4/4 on UI-TARS; GPT-5.5 scores 5/5 on UI-TARS but 4/4 on doubao. The specific weaknesses differ: Claude conflates procedural phases in UI-TARS, while GPT loses quantitative specificity in doubao.
  - Importance: This suggests that summarization quality may depend on trajectory characteristics (e.g., loop-heavy vs. phase-transition-heavy) rather than being uniformly better for one model.
- **Finding:** Neither model flags that the task outcome was a failure despite both agents appearing to complete the task.
  - Evidence: Both trajectories have success_binary=False, yet all four summaries describe the agents as successfully applying strikethrough and terminating with DONE, without noting any indication of failure.
  - Importance: This reveals a critical gap in trajectory summarization: when an agent appears to complete a task but actually fails, summarizers that only describe actions without evaluating outcomes will miss the failure signal. This matters for downstream analysis of agent capabilities.
- **Finding:** Quantitative specificity about repetitive actions (e.g., number of undo clicks) varies significantly between models and affects perceived trajectory understanding.
  - Evidence: Claude specifies '15-20 times' for undo clicks in the doubao trajectory while GPT says 'many times'; the judge penalizes GPT for this vagueness (specificity score 3 vs. Claude's 5).
  - Importance: Repetitive loops are a common failure pattern in agent trajectories, and precise characterization of their extent is important for understanding agent behavior and debugging.
- **Finding:** Distinguishing between procedurally distinct failure phases (e.g., before vs. after entering edit mode) is important but challenging for summarizers.
  - Evidence: In the UI-TARS trajectory, GPT correctly separates box-moving errors from text-scrambling errors around the double-click transition, while Claude lumps them together. The judge notes this as a minor error for Claude.
  - Importance: Phase transitions in agent behavior (where the nature of errors changes) carry diagnostic information about what the agent learned or failed to learn, and conflating them reduces the summary's analytical value.

## ac9bb6cb-1888-43ab-81e4-a98a547918cd

- Domain: `libreoffice_impress`
- Pair outcome: `both_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

When both trajectories in a pair fail but through different mechanisms — one with an obvious premature termination and another with a subtler procedural gap — summarization models reliably detect the obvious failure but may hallucinate success for the subtle one. Claude's summary explicitly claims the UI-TARS agent 'successfully modified the slide number color to red' despite a ground-truth failure, illustrating how surface-level workflow completeness can mislead summarizers into fabricating positive outcomes.

### Trajectory contrast

Both trajectories fail to change the slide number color to red, but they take fundamentally different approaches. The doubao agent works in normal slide view, enabling the slide number via Insert > Header and Footer, then attempts to change the color via the Properties panel but terminates before selecting red. The UI-TARS agent enters Master Slide view via View > Master Slide, clicks the slide number text box there, clicks the font color button, then closes Master View and saves — but also fails to actually apply red.

Both agents fail (success=0.0). The doubao agent's failure is clearly attributable to terminating prematurely before selecting a color from the picker. The UI-TARS agent's failure is more subtle — it went through more steps (closing master view, saving) but likely failed because it didn't select the text within the text box or didn't explicitly choose red from a color picker.

### Main qualitative findings

- **Finding:** Summarizers are more likely to correctly identify failure when the failure mode is obvious (premature termination) than when it is subtle (missing intermediate steps like text selection or color picker usage).
  - Evidence: Both models correctly note the doubao agent's premature DONE before color selection. But for the UI-TARS trajectory, where the agent completed more steps but still failed, Claude explicitly claims success and GPT-5.5 only hedges rather than noting failure.
  - Importance: This reveals a systematic bias in trajectory summarization: models infer success from the appearance of a complete workflow, even when critical micro-steps are missing. This is dangerous for downstream use of summaries in debugging or evaluation.
- **Finding:** Claude's failure awareness is inconsistent across paired trajectories of the same task, correctly identifying failure in one but hallucinating success in the other.
  - Evidence: Claude's doubao summary says 'the trajectory does not confirm that a red color was explicitly selected' while its UI-TARS summary says 'The agent successfully modified the slide number color to red' — both trajectories failed with success=0.0.
  - Importance: This inconsistency within the same task pair demonstrates that failure detection is not robust and depends heavily on surface-level trajectory characteristics rather than actual outcome verification.
- **Finding:** GPT-5.5's hedging language ('apparently setting') is a safer strategy than Claude's definitive claims when outcome is uncertain, but still falls short of explicit failure acknowledgment.
  - Evidence: GPT-5.5 uses 'apparently setting the slide number text color to red' for UI-TARS, receiving only minor hallucination severity from the judge, while Claude's definitive 'Changed the font color to red' and 'successfully modified' received major hallucination severity.
  - Importance: Hedging is a useful summarization strategy when the trajectory evidence is ambiguous, but ideal summaries should go further and note when critical verification steps (like confirming color selection) are absent.
- **Finding:** Both models achieve high judge scores for the doubao trajectory (Coverage 5, Factuality 5) but diverge on the UI-TARS trajectory, where Claude's factuality drops to 3 due to the success hallucination.
  - Evidence: Claude: doubao Factuality=5, UI-TARS Factuality=3. GPT-5.5: doubao Factuality=5, UI-TARS Factuality=4.
  - Importance: This quantitatively confirms that the more ambiguous failure mode in the UI-TARS trajectory is harder for models to summarize accurately, and that factuality scores can diverge significantly within the same task pair.

## 0e5303d4-8820-42f6-b18d-daf7e633de21

- Domain: `multi_apps`
- Pair outcome: `both_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

When both trajectories fail but through fundamentally different mechanisms—one via catastrophic interaction failure (stuck loop) and another via subtle task compliance failure (wrong save location)—summarization models more reliably capture obvious failures than subtle ones. GPT-5.5 better preserved the UI-TARS save-location deviation, while Claude excelled at detailing the doubao stuck-loop failure, suggesting that failure-awareness in trajectory summarization is not a single capability but varies by failure type.

### Trajectory contrast

Both trajectories fail the task but in very different ways. The doubao agent downloads only the Week 1 PDF and then gets stuck in a loop trying to click the Week 2 link for ~80 remaining steps. The UI-TARS agent successfully downloads all PDFs for Weeks 1-9 but saves them to the default Downloads folder instead of the specified 'opened folder', which constitutes a different kind of failure.

Both are scored as failures (0.0), but the nature of failure is drastically different. The doubao agent fails due to a navigation/interaction bug that prevents progress past Week 1. The UI-TARS agent completes the download workflow for all weeks but fails on the save-location requirement. These represent fundamentally different failure modes: catastrophic interaction failure vs. subtle task compliance failure.

### Main qualitative findings

- **Finding:** Different failure modes require different summarization strategies, and models vary in their ability to flag subtle compliance failures vs. obvious interaction failures.
  - Evidence: Both models perfectly captured the doubao agent's obvious stuck-loop failure. However, for the UI-TARS agent's subtler save-location failure, GPT-5.5 explicitly flagged the deviation while Claude only vaguely referenced 'default download location'. Claude scored 4 on factuality for UI-TARS vs. GPT-5.5's perfect 5.
  - Importance: Trajectory summarizers must handle a spectrum of failure types. Catastrophic failures (stuck loops) are easy to detect and describe, but subtle task compliance failures (wrong save location) require the summarizer to understand the task requirements and compare them against agent behavior.
- **Finding:** Claude's doubao summary demonstrates that highly detailed failure descriptions (coordinate ranges, attempt counts) can achieve perfect scores, suggesting evaluators value specificity in failure characterization.
  - Evidence: Claude's doubao summary received all 5s and mentioned '80+ repeated click attempts at coordinates around (483–487, 408–411)', while GPT-5.5's less detailed version scored 4 on coverage and specificity.
  - Importance: For trajectory summarization, concrete details about failure behavior (not just that failure occurred) are valued by human evaluators and may be important for downstream debugging or analysis.
- **Finding:** Both-failure pairs with different failure modes are particularly revealing for summarization quality because they test whether models can distinguish between types of failure rather than just detecting success vs. failure.
  - Evidence: The doubao agent failed by getting stuck (1/9 downloads), while UI-TARS failed by saving to the wrong location (9/9 downloads, wrong folder). Both scored 0.0 on success, but the summaries needed to convey very different stories.
  - Importance: This demonstrates that binary success labels are insufficient for evaluating summarization quality; the nature and specifics of failure matter significantly.
- **Finding:** Automatic metrics (ROUGE-L, BERTScore) show minimal differentiation between summaries despite meaningful quality differences identified by judges.
  - Evidence: For the doubao trajectory, Claude scored all 5s while GPT-5.5 scored 4s on some dimensions, yet their ROUGE-L scores were similar (0.367 vs. 0.385). For UI-TARS, GPT-5.5 achieved perfect judge scores while Claude had a minor factuality issue, but ROUGE-L differences were small (0.396 vs. 0.366).
  - Importance: This reinforces that automatic metrics are poor proxies for summarization quality in agent trajectory contexts, particularly for capturing failure awareness and task compliance understanding.

## 58565672-7bfe-48ab-b828-db349231de6b

- Domain: `multi_apps`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this mixed success/failure pair, both evaluated models accurately captured procedural steps but failed to explicitly flag the unsuccessful trajectory's failure, illustrating a systematic blind spot in trajectory summarization: when an agent's steps appear procedurally reasonable but the task ultimately fails, summarizers tend to present the trajectory as successful, obscuring critical outcome information needed for debugging and comparative analysis.

### Trajectory contrast

Both trajectories attempt the same task (open the first link in the latest email in the Bills folder in a new Chrome tab), but they operate on different email environments. The successful trajectory (doubao) identifies the latest email as an AWS invoice and clicks the 'Billing & Cost Management Page' link directly. The failing trajectory (UI-TARS) identifies the latest email as a Twitter/X receipt and right-clicks a help.twitter.com link, selecting 'Open Link In Browser' from the context menu. Despite seemingly correct procedural steps, the UI-TARS trajectory fails (score 0.0), possibly because the link did not open in a new Chrome tab as required or the wrong email was selected.

The successful agent clicked the link directly, which triggered Thunderbird to open it in Chrome. The failing agent used a right-click context menu approach ('Open Link In Browser'), which may not have resulted in a new Chrome tab as required. The task failure could also relate to the email environment differing or the evaluation criteria not being met despite apparently reasonable steps.

### Main qualitative findings

- **Finding:** Both models fail to explicitly flag task failure in the unsuccessful trajectory, presenting procedurally reasonable steps as if they led to success.
  - Evidence: The UI-TARS trajectory has success_raw: 0.0, yet both summaries describe the steps without noting failure. Claude adds confident interpretive language ('determined that Chrome was likely the default browser'), while GPT-5.5 only subtly hedges ('without showing the resulting Chrome tab').
  - Importance: For trajectory summarization to be useful for debugging or learning, summaries must distinguish between successful and failed executions, especially when the procedural steps appear superficially correct.
- **Finding:** Claude Sonnet achieves higher specificity but at the cost of minor hallucinations and unsupported interpretive claims.
  - Evidence: Claude's summary of the failing trajectory includes 'opened the Thunderbird email client' (hallucination, judged as minor) and 'determined that Chrome was likely the default browser' (interpretive claim). GPT-5.5 avoids these errors but is slightly less specific about the email subject in the successful trajectory.
  - Importance: This illustrates a specificity-accuracy tradeoff: models that generate more detailed summaries may also introduce fabricated details, which is particularly problematic when the trajectory outcome is ambiguous.
- **Finding:** The procedural difference between direct click and right-click context menu is preserved by both models, which is critical for understanding the success/failure divergence.
  - Evidence: Both models correctly note that the successful trajectory used a direct click while the failing trajectory used right-click → 'Open Link In Browser'. This procedural distinction is the most likely explanation for the outcome difference.
  - Importance: Preserving method-level procedural details is essential for trajectory summarization, as seemingly equivalent approaches can lead to different outcomes in GUI automation.
- **Finding:** Despite high judge scores (mostly 5s) for both models on both trajectories, neither model adequately represents the failure status, suggesting judge rubrics may not sufficiently penalize failure omission.
  - Evidence: Both models receive Coverage: 5, Factuality: 4-5, and Omission severity: none on the failing trajectory, yet neither mentions the task failed. The judge annotations only flag minor issues (hallucination for Claude, no errors for GPT-5.5).
  - Importance: This suggests that current evaluation rubrics may be insufficient for assessing whether summaries capture task outcomes, a critical dimension for trajectory analysis.

## c2751594-0cd5-4088-be1b-b5f2f9ec97c4

- Domain: `multi_apps`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this mixed success/failure pair where both agents followed nearly identical procedures but diverged in terminal outcome, both evaluated models correctly preserved the critical FAIL vs. DONE distinction. However, GPT-5.5 better captured intermediate procedural struggles (failed minimize attempts) in the successful trajectory, suggesting that preserving micro-level agent behaviors—not just high-level steps and outcomes—is important for distinguishing trajectory quality. This case also reveals that automatic metrics like ROUGE-L can diverge substantially from human judgments when summaries are equally accurate but structurally different.

### Trajectory contrast

Both agents followed nearly identical procedures: finding the email in the Notes folder, saving the attachment, extracting the first image from the document, and attempting to set it as the desktop background. The doubao agent saved the attachment directly to disk then opened it, while UI-TARS opened it directly with LibreOffice Writer. The doubao agent saved the image to Desktop as 'exported_image.png' while UI-TARS saved it to Pictures as 'bg_image.png'. The doubao agent ended with FAIL despite apparently completing all steps, while UI-TARS ended with DONE and achieved success. UI-TARS also had notable failed minimize attempts before closing windows.

The doubao agent performed all the correct steps but terminated with a FAIL action, suggesting either the agent detected an issue not visible in the summary or it made an incorrect self-assessment. UI-TARS completed successfully despite struggling with window minimization. The procedural paths were very similar, making the outcome difference subtle and potentially related to a final configuration step or the agent's self-evaluation logic.

### Main qualitative findings

- **Finding:** Both models correctly preserved the critical FAIL vs. DONE distinction between the paired trajectories.
  - Evidence: GPT-5.5 wrote 'The trajectory ended with a FAIL status rather than DONE, so successful completion was not confirmed.' Claude wrote 'the agent issued a FAIL action, indicating the task was not successfully completed.' Both received perfect factuality scores for the doubao trajectory.
  - Importance: Preserving terminal success/failure status is essential for trajectory summarization, especially when the procedural steps appear nearly identical between success and failure cases.
- **Finding:** GPT-5.5 better captured intermediate struggles (failed minimize attempts) in the successful trajectory, while Claude omitted them.
  - Evidence: GPT-5.5: 'attempted several times to minimize LibreOffice Writer, eventually closed it.' Claude's UI-TARS summary simply says 'closed the LibreOffice Writer window.' Judge flagged this as a minor omission for Claude.
  - Importance: Intermediate failures and workarounds are important procedural details that distinguish agent behaviors and inform debugging or improvement efforts.
- **Finding:** When procedural steps are nearly identical between success and failure trajectories, the terminal action and subtle differences become the most important elements to preserve.
  - Evidence: Both trajectories followed the same high-level procedure (find email → save attachment → extract image → set background), differing mainly in file paths, window management, and terminal action. Both models correctly identified these differences.
  - Importance: This case demonstrates that trajectory summarization must go beyond high-level procedure description to capture the specific details that differentiate success from failure.
- **Finding:** Automatic metrics (ROUGE-L, BERTScore) showed notable variation between models despite identical perfect judge scores for the doubao trajectory.
  - Evidence: For the doubao trajectory, GPT-5.5 had ROUGE-L 0.531 and BERTScore 0.481, while Claude had ROUGE-L 0.384 and BERTScore 0.314, yet both received 5/5 on all judge dimensions.
  - Importance: This highlights the limitation of reference-based automatic metrics for evaluating trajectory summaries, as structurally different but equally accurate summaries can receive very different automatic scores.

## da52d699-e8d2-4dc5-9191-a2199e0b6a9b

- Domain: `multi_apps`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

In this mixed success/failure pair, both evaluated models produced accurate descriptions of agent actions but failed to note a critical task-level omission (not visiting a required website) that the human gold summary explicitly flagged. This illustrates a systematic blind spot in model-generated trajectory summaries: they faithfully describe what agents did but fail to identify what agents should have done, making failed trajectories appear procedurally sound and obscuring the diagnostic information most valuable for understanding failure.

### Trajectory contrast

The doubao agent (failure) never visited the required howlongtoread.com website and instead relied solely on spreadsheet column I to identify 'The Shining' as the slowest reading pace book. The UI-TARS agent (success) correctly computed words per day by dividing word count (column G) by days (column I) and identified 'Out of the Silent Planet' as the correct answer. The two trajectories also differ in procedural struggles: doubao repeatedly opened and closed files in a disorganized manner, while UI-TARS had difficulties minimizing windows and pasting text but ultimately completed the task correctly.

The doubao agent failed because it used the wrong methodology (reading a raw column value rather than computing words per day) and never consulted the required website, arriving at the wrong answer ('The Shining'). The UI-TARS agent succeeded by performing the correct mental calculation and writing the correct answer ('Out of the Silent Planet').

### Main qualitative findings

- **Finding:** Both evaluated models fail to note the omission of a required procedural step (visiting howlongtoread.com) in the failed trajectory, despite the human gold summary explicitly flagging this.
  - Evidence: The human gold summary for doubao states 'The agent never navigates to the website mentioned in the prompt.' Neither Claude nor GPT-5.5 mention this. The judge for GPT-5.5 noted this as a minor omission, but the judge for Claude did not flag it at all, giving a perfect score.
  - Importance: This demonstrates that model summarizers may systematically fail to identify task-level omissions—steps the agent should have taken but didn't—which are critical for understanding why a trajectory failed.
- **Finding:** Model summaries can make a failed trajectory appear procedurally sound by accurately describing what happened without noting what should have happened.
  - Evidence: Claude's summary of the doubao trajectory reads as a coherent, well-executed procedure: the agent examined data, identified a value, and wrote it to a document. Without knowledge that the answer is wrong and the methodology flawed, a reader would not recognize this as a failure.
  - Importance: For trajectory summarization to be useful for debugging or learning, summaries must preserve failure signals, not just action sequences. This is especially important in paired comparisons where the contrast between success and failure is the key information.
- **Finding:** Both models achieve high judge scores on the failed trajectory despite missing the most important failure-related detail.
  - Evidence: Claude received 5/5 on all dimensions with no errors flagged for the doubao summary. GPT-5.5 received 4-5 scores with only minor errors noted. Yet both miss the website omission that the human gold summary highlights.
  - Importance: This suggests that current evaluation frameworks may not adequately penalize the omission of failure-diagnostic information, potentially because judges evaluate coverage of what happened rather than what should have happened.
- **Finding:** Claude provides notably more specific numerical details than GPT-5.5, particularly for the successful trajectory.
  - Evidence: Claude includes '47,840 words / 36.13 days ≈ 1,324 words/day' for the UI-TARS trajectory, while GPT-5.5 describes the reasoning more abstractly. The judge noted this as a minor specificity loss for GPT-5.5.
  - Importance: Numerical specificity aids in verifying agent reasoning and is particularly valuable when the correctness of a calculation determines task success.

## 8ba5ae7a-5ae5-4eab-9fcc-5dd4fe3abf89

- Domain: `vlc`
- Pair outcome: `both_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

When an agent changes the wrong setting in a plausible-looking procedural sequence, summarizers may misrepresent the error as task success. In this VLC case, one model explicitly framed a snapshots-directory change as a recording-folder change, while the other remained factually neutral but omitted the error diagnosis—illustrating a tension between conservative reporting and explicit failure attribution that trajectory summarization systems must navigate.

### Trajectory contrast

Both agents fail to correctly change the VLC recording folder to Desktop, but they fail in different ways. The doubao agent stays in Simple Preferences and changes the wrong setting (Video snapshots directory instead of the recording directory). The UI-TARS agent correctly identifies the need to switch to Advanced Preferences and navigates to the Record stream output setting, entering ~/Desktop/ as the destination prefix, but this also does not achieve the task goal (both scored 0.0).

Both trajectories are failures, but they represent qualitatively different failure modes. The doubao agent makes a clear categorical error (wrong setting entirely). The UI-TARS agent follows a more sophisticated path and finds a plausibly correct setting, but still fails—possibly because ~/Desktop/ is not the correct absolute path or the setting doesn't control the intended recording folder.

### Main qualitative findings

- **Finding:** Summarizers can misinterpret wrong-setting errors as task success when the procedural steps superficially resemble correct behavior.
  - Evidence: Claude Sonnet 4.6 states the doubao agent 'modified the VLC recording storage folder to the Desktop' when it actually changed the Video snapshots directory. The judge flagged this as a major hallucination.
  - Importance: This demonstrates that models may infer success from procedural completion without verifying whether the correct setting was modified, a critical failure mode for trajectory summarization.
- **Finding:** Neutral factual reporting without explicit error diagnosis can be preferable to incorrect success framing.
  - Evidence: GPT-5.5's doubao summary describes the steps without claiming success (Factuality: 5, Hallucination: none), while Claude's summary claims success (Factuality: 3, Hallucination: major). GPT-5.5's omission of the error diagnosis was rated as only minor severity.
  - Importance: This suggests that when models are uncertain about outcomes, conservative factual reporting is safer than inferring task completion.
- **Finding:** Both models perform excellently when the trajectory involves a clear, coherent procedural path, even if the task ultimately fails.
  - Evidence: For the UI-TARS trajectory, both models received perfect scores (Coverage: 5, Factuality: 5, all dimensions: 5) with no errors flagged.
  - Importance: This indicates that summarization quality may depend more on trajectory coherence than on success/failure status—well-structured failing trajectories can be summarized as accurately as successful ones.
- **Finding:** Different failure modes within the same task create asymmetric summarization difficulty.
  - Evidence: The doubao trajectory's subtle wrong-setting error was harder to summarize correctly (Claude made a major error, GPT had a minor omission) compared to the UI-TARS trajectory's more transparent procedural path (both models scored perfectly).
  - Importance: Subtle categorical errors (changing the wrong setting) pose greater challenges for summarizers than complex but coherent navigation paths, suggesting error detection is a key capability gap.

## 847a96b6-df94-4927-97e6-8cc9ea66ced7

- Domain: `vs_code`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

This paired case demonstrates that both evaluated models reliably preserve failure states without optimistic smoothing, even across 100-step perseverative loops. Claude's consistently higher specificity scores (5 vs. 3-4) suggest it better captures the granular details of repetitive failure patterns—such as step ranges and attempt counts—that are critical for distinguishing between agents that perseverate indefinitely versus those that adaptively recover.

### Trajectory contrast

Both agents successfully open the first workspace and then get stuck repeatedly clicking the File menu when trying to open the second. The doubao agent (100 steps, failure) remains stuck in the File menu clicking loop for ~90 steps without recovery. The UI-TARS agent (16 steps, success) also gets stuck but recovers by switching to the Command Palette via Ctrl+Shift+P, then issues a FAIL action—yet is marked as task-successful (success_raw=1.0), suggesting the task was actually completed despite the agent's self-reported failure.

The success/failure labels are somewhat paradoxical: the doubao agent (marked failure) never opens the second workspace, while the UI-TARS agent (marked success) also explicitly issues a FAIL action and does not visibly complete the second workspace opening within the trajectory. The success=True for UI-TARS may indicate that the Command Palette action or some post-trajectory state resulted in task completion, or that the evaluation metric detected both workspaces were open. Both human gold summaries describe incomplete task execution, making this an interesting case where ground-truth success labels diverge from apparent trajectory behavior.

### Main qualitative findings

- **Finding:** Both models reliably preserve failure states and do not hallucinate success when trajectories end without task completion.
  - Evidence: For both the doubao (failure) and UI-TARS (self-reported FAIL) trajectories, both models explicitly state the task was not completed and the second workspace was never opened. Judge hallucination severity is 'none' across all four summaries.
  - Importance: This demonstrates that modern LLMs can faithfully represent agent failures without optimistic bias, which is critical for trajectory summarization in evaluation contexts.
- **Finding:** Claude consistently provides higher specificity than GPT-5.5, particularly for repetitive failure patterns, without sacrificing accuracy.
  - Evidence: Claude's doubao summary includes ~90 repeated attempts, coordinate variations, step ranges (9-100), and the WAIT action, earning Specificity=5 vs GPT-5.5's Specificity=3. Similarly for UI-TARS, Claude earns Specificity=5 vs GPT-5.5's Specificity=4.
  - Importance: For debugging and understanding agent failure modes, specificity about repetitive behaviors (how many times, over what step range) is valuable for identifying whether an agent has any recovery mechanism.
- **Finding:** The key behavioral contrast between trajectories—perseveration vs. adaptive recovery—is preserved by both models but with different levels of emphasis.
  - Evidence: Both models note the doubao agent's ~90-step loop without strategy change and the UI-TARS agent's switch to Command Palette. Claude structures this as a distinct section ('Final attempt via Command Palette') making the strategic shift more prominent.
  - Importance: Preserving the contrast between perseverative failure and adaptive recovery is essential for paired trajectory analysis, as it reveals differences in agent capabilities.
- **Finding:** Ground-truth success labels can diverge from observable trajectory behavior, creating a challenge for summarizers.
  - Evidence: UI-TARS is marked success=True despite the agent issuing a FAIL action and the human gold summary describing incomplete execution. Neither model addresses this discrepancy, correctly summarizing only what is observable in the trajectory.
  - Importance: This highlights that trajectory summarization should focus on observable behavior rather than external success labels, and that paired cases with paradoxical labels require careful interpretation.

## e2b5e914-ffe1-44d2-8e92-58f8c5d92bb2

- Domain: `vs_code`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `high`

### Paper-ready takeaway

When summarizing failed trajectories that include error-recovery sequences, both GPT-5.5 and Claude Sonnet 4.6 accurately describe the recovery steps but fail to flag the trajectory as ultimately unsuccessful, suggesting that current summarization models conflate attempted recovery with task success—a critical distinction for trajectory analysis.

### Trajectory contrast

Both agents attempted to disable Python missing import error reporting in VS Code settings. The failed agent (doubao) took 14 steps, encountered errors during value entry (e.g., 'warningnone' concatenation), and had to recover by selecting all text and overwriting with correct JSON. The successful agent (UI-TARS) completed the task cleanly in 8 steps with no errors, using a more direct search query and straightforward editing.

The failed agent's longer trajectory reflects procedural missteps—using the settings UI dropdown incorrectly, accidentally concatenating values, and needing a full overwrite to recover. Despite the recovery appearing correct in the final state, the task was marked as failed (possibly due to formatting or other evaluation criteria). The successful agent followed a clean, efficient path with no errors.

### Main qualitative findings

- **Finding:** Both models fail to explicitly mark the failed trajectory as unsuccessful, despite accurately describing the error-recovery process.
  - Evidence: Claude states 'The final state had the settings.json content replaced with the correct configuration,' and GPT-5.5 simply describes the recovery without noting failure. The ground truth marks this trajectory as failed (success_raw: 0.0).
  - Importance: Trajectory summaries that describe recovery steps but omit the ultimate failure status can mislead downstream consumers into thinking the agent succeeded. Summarizers should distinguish between attempted recovery and actual task success.
- **Finding:** Claude achieves higher specificity on the failed trajectory while GPT-5.5 uses vaguer language, yet both receive high judge scores.
  - Evidence: Claude's failed-trajectory summary scores 5/5 on specificity while GPT-5.5 scores 3/5. GPT-5.5 uses phrases like 'interacted with' and 'opened/used' instead of naming specific UI elements and actions.
  - Importance: Procedural specificity matters for reconstructing agent behavior, especially in error cases where the exact sequence of missteps is informative for debugging or improvement.
- **Finding:** The successful trajectory is straightforward enough that both models produce near-perfect summaries, suggesting that summarization difficulty scales with trajectory complexity and error presence.
  - Evidence: Both models receive perfect 5/5 scores across all judge dimensions for the successful (8-step) trajectory, while the failed (14-step) trajectory shows differentiation between models.
  - Importance: This supports the hypothesis that error-laden, longer trajectories are more challenging to summarize and serve as better discriminators of summarization quality.
- **Finding:** The contrast between trajectories reveals different entry points to VS Code settings (gear icon vs. File menu), which both models correctly preserve.
  - Evidence: For the successful trajectory, both models mention the gear icon; for the failed trajectory, both mention File > Preferences > Settings. These match the respective gold summaries.
  - Importance: Preserving agent-specific procedural choices is important for understanding behavioral differences across agents, even when the task goal is identical.

## b4f95342-463e-4179-8c3f-193cd7241fb2

- Domain: `chrome`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

This paired case reveals that when two trajectories are procedurally identical but carry different success/failure labels, both evaluated summarization models faithfully describe the shared observable behavior without fabricating outcome differences—demonstrating behavioral fidelity but also highlighting that success labels may not always correspond to distinguishable trajectory-level differences that summarizers can capture.

### Trajectory contrast

Both trajectories follow nearly identical procedures: search for 'Diamond' on Recreation.gov, click the DIAMOND campground result, scroll down, click 'Next Available,' encounter an error popup, click 'Refresh,' and then wait for the remaining ~90 steps without further action. The doubao agent is marked as failure (0.0) while the UI-TARS agent is marked as success (1.0), despite both exhibiting the same observable behavior and outcome.

The success/failure labels appear paradoxical given the nearly identical trajectories. Both agents encounter the same error and end up waiting indefinitely. The success label for UI-TARS may reflect an evaluation criterion that considers the agent's actions sufficient (e.g., clicking 'Next Available' counts as task completion) or a difference in the underlying page state not visible in the trajectory summaries. The human gold summaries for both are also nearly identical, reinforcing that the observable behavior was the same.

### Main qualitative findings

- **Finding:** When paired trajectories are procedurally identical but have different success labels, both summarization models produce nearly identical summaries, faithfully reflecting the observed behavior rather than the labels.
  - Evidence: Both GPT-5.5 and Claude Sonnet 4.6 produced summaries for the doubao (failure) and UI-TARS (success) trajectories that describe the same sequence of actions and the same stalled outcome. Neither model attempted to differentiate the summaries based on the success/failure metadata.
  - Importance: This demonstrates that trajectory summarizers focus on observable behavior rather than external labels, which is desirable for faithful summarization but raises questions about whether summaries should incorporate task outcome information.
- **Finding:** Both models achieved perfect or near-perfect judge scores across all dimensions for both trajectories, suggesting that when trajectories are straightforward and procedurally clear, current models can summarize them reliably.
  - Evidence: All four summaries received Coverage 5, Factuality 5, Temporal order 5, and Procedural usefulness 5. The only variation was GPT-5.5 receiving Specificity 4 (vs. Claude's 5) for both trajectories.
  - Importance: This case establishes a performance ceiling for simple, linear trajectories and suggests that differentiation between models may emerge primarily on more complex or ambiguous cases.
- **Finding:** The paradoxical success/failure labels for identical trajectories highlight a limitation of using success labels as ground truth for summarization evaluation.
  - Evidence: The human gold summaries for both trajectories are nearly word-for-word identical, and both describe the same error-and-wait pattern. Yet one is labeled success (1.0) and the other failure (0.0), suggesting the evaluation criterion may depend on factors not captured in the trajectory itself.
  - Importance: This matters for trajectory summarization research because it shows that success/failure labels may not always correspond to observable behavioral differences, complicating any analysis that assumes summaries should reflect task outcomes.
- **Finding:** Claude Sonnet 4.6 consistently provided slightly more specific details (step ranges, absence of DONE action) compared to GPT-5.5, though this did not substantially affect overall quality scores.
  - Evidence: Claude mentioned 'steps 10 through 100' and 'never issued a DONE action' for the doubao trajectory, while GPT-5.5 used vaguer language like 'repeatedly waited for the page to load through the remaining steps.' Judge scored Claude at Specificity 5 and GPT-5.5 at Specificity 4 for both trajectories.
  - Importance: This suggests that specificity about step counts and meta-actions (like DONE) is a consistent differentiator between models, even when overall summary quality is comparable.

## 42e0a640-4f19-4b28-973d-729602b5a4a7

- Domain: `libreoffice_calc`
- Pair outcome: `both_success`
- Recommended paper use: `medium`

### Paper-ready takeaway

In this both-success paired case with differing procedural complexity, Claude Sonnet 4.6 achieved perfect judge scores on both trajectories by faithfully preserving error-recovery details and specific cell references, while GPT-5.5 introduced misleading hedging language for the clean trajectory and lost specificity for the complex one—despite GPT-5.5 scoring higher on automatic reference-based metrics, highlighting the gap between lexical overlap and semantic fidelity in trajectory summarization.

### Trajectory contrast

Both trajectories successfully complete the same task (computing sums and placing them in Sheet2), but the UI-TARS trajectory takes a longer, more error-prone path (30 steps vs 17). The doubao agent directly enters cross-sheet SUM formulas in Sheet2, while the UI-TARS agent first tries computing sums in Sheet1 and copy-pasting them, encounters #REF! errors, and only then switches to cross-sheet formulas.

Both succeed, but the UI-TARS trajectory includes a significant error-recovery episode (failed copy-paste producing #REF! errors, multiple retry attempts) before arriving at the same correct solution. The doubao trajectory is a clean, direct execution.

### Main qualitative findings

- **Finding:** Claude Sonnet 4.6 achieves perfect judge scores on both trajectories despite lower automatic metrics, illustrating a disconnect between reference-based metrics and semantic quality.
  - Evidence: Claude gets Coverage/Factuality/Specificity all 5/5 for both trajectories, but ROUGE-L is 0.39 and 0.36 respectively. GPT-5.5 has higher ROUGE-L (0.59, 0.50) but lower judge scores (4/4/3 and 4/5/4).
  - Importance: This demonstrates that automatic metrics may penalize well-written summaries that use different phrasing from gold references, reinforcing the need for judge-based evaluation.
- **Finding:** GPT-5.5 introduces misleading hedging language for the clean trajectory, implying agent uncertainty that does not exist.
  - Evidence: Phrases like 'assumed it was Sheet2' and 'it believed was A2:A20' in the doubao summary, flagged by the judge as misleading framing.
  - Importance: Summarizers should not inject epistemic uncertainty into descriptions of deterministic agent actions. This could mislead downstream consumers about agent reliability.
- **Finding:** Both models successfully differentiate between the clean and error-recovery trajectories, preserving the key procedural contrast.
  - Evidence: Both models' UI-TARS summaries describe the #REF! error and strategy shift, while their doubao summaries describe a direct workflow. The structural difference between the paired trajectories is maintained.
  - Importance: For paired trajectory analysis, it is critical that summaries preserve whether an agent took a direct path versus an error-recovery path, even when both succeed.
- **Finding:** Specificity loss in GPT-5.5 manifests as omission of cell references and collapsing of distinct retry attempts.
  - Evidence: GPT-5.5's UI-TARS summary omits A21/B21 cell references and merges two failed paste attempts; judge scores Specificity at 4 vs Claude's 5.
  - Importance: For procedural reconstruction, specific cell references and the number of retry attempts matter for understanding agent behavior patterns.

## 15aece23-a215-4579-91b4-69eec72e18da

- Domain: `libreoffice_impress`
- Pair outcome: `both_success`
- Recommended paper use: `medium`

### Paper-ready takeaway

Even when both trajectories succeed at the same task, the intermediate debugging strategies can differ substantially (iterative coordinate adjustment vs. selection-mode correction); Claude's summaries better preserve these procedural distinctions through coordinate-level specificity, while GPT-5.5 tends to compress multiple distinct attempts into vaguer descriptions, losing information about the agent's step-by-step problem-solving process.

### Trajectory contrast

Both trajectories succeed at moving the title of slide 2 to the bottom, but they differ in the nature of intermediate failures. The doubao agent makes three drag attempts, adjusting the grab point each time, with the first two failing. The UI-TARS agent makes one failed drag (likely entering text-editing mode instead of moving the box), then re-selects the text box by clicking its border, and succeeds on the second drag.

Both are successful (True+True), but the intermediate debugging strategies differ: doubao adjusts the starting coordinates of the drag across three attempts, while UI-TARS diagnoses the problem as a selection-mode issue (text editing vs. object selection) and fixes it by clicking the border before re-dragging.

### Main qualitative findings

- **Finding:** Both models correctly preserve the distinct debugging strategies between the two trajectories despite both being successful.
  - Evidence: Claude and GPT-5.5 both distinguish doubao's iterative coordinate adjustment from UI-TARS's selection-mode correction. Claude's doubao summary mentions 'adjusting the grab point each time' and GPT-5.5's UI-TARS summary mentions 'recognized that the first drag may have affected the text content rather than the entire title box.'
  - Importance: This shows that both models can differentiate procedural strategies even when outcomes are identical, which is critical for trajectory summarization that aims to capture agent behavior rather than just results.
- **Finding:** Claude consistently provides higher specificity (coordinates, precise step enumeration) while GPT-5.5 provides more concise but less detailed summaries.
  - Evidence: Claude's doubao summary includes specific y-values (y=297, y=912, y=279, y=927, y=274, y=910) and x-values, earning Specificity=5. GPT-5.5's doubao summary omits these, earning Specificity=3. The pattern repeats for UI-TARS (Claude Specificity=5, GPT-5.5 Specificity=4).
  - Importance: Coordinate-level detail matters for reconstructing agent behavior in GUI tasks and understanding why specific actions failed, making this a meaningful quality difference for trajectory summarization.
- **Finding:** Both models express uncertainty about the doubao trajectory's final success despite the task being marked successful.
  - Evidence: Claude states 'It is unclear from the trajectory whether the final drag attempt was successful.' GPT-5.5 states 'The trajectory does not show a visible confirmation of whether the title actually moved successfully.' The gold summary definitively states the third attempt succeeded.
  - Importance: This reveals a systematic tendency for summarizer models to hedge on success when visual confirmation is ambiguous in screenshots, even when the task outcome is clearly successful. This could be a limitation when summaries are used for downstream analysis.
- **Finding:** GPT-5.5's doubao summary conflates the second and third drag attempts, describing 'twice from around the title area, then tried again' rather than clearly delineating three distinct attempts.
  - Evidence: The judge flagged this: 'Summary B says attempted to drag... twice from around the title area, then tried again but does not clearly enumerate three distinct attempts with their distinguishing characteristics.'
  - Importance: Merging distinct steps obscures the agent's iterative debugging process, which is a key behavioral signal in trajectory data.

## 8979838c-54a5-4454-a2b8-3d135a1a5c8f

- Domain: `libreoffice_impress`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

In this mixed success/failure case, both evaluated models reliably identified the failing agent's premature termination and preserved the successful agent's error-recovery workflow, demonstrating that current summarization models can maintain critical outcome distinctions in paired trajectories. However, the case also reveals that automatic metrics like ROUGE-L and BERTScore diverge substantially from human judgments, with score differences of up to 0.09 ROUGE-L between models that received identical perfect ratings from judges.

### Trajectory contrast

Both agents successfully changed the slide background to purple using the Properties panel. The failing agent (doubao) copied the title text but issued DONE without pasting it into the notes section. The successful agent (UI-TARS) completed the full workflow: it made a drag-selection mistake, undid it, correctly copied the title, navigated to the notes pane via the View menu (after first checking Insert menu), pasted the title, and saved.

The doubao agent failed because it stopped after copying the title text without ever navigating to or pasting into the notes area. The UI-TARS agent succeeded despite making errors (accidental text box move, wrong menu exploration) because it recovered from mistakes and completed all required steps including pasting into notes and saving.

### Main qualitative findings

- **Finding:** Both evaluated models reliably detect and report premature task termination as a failure mode.
  - Evidence: Both GPT-5.5 and Claude Sonnet 4.6 explicitly state that the doubao agent issued DONE without pasting the title into notes, matching the human gold summary's characterization of the failure.
  - Importance: Accurate failure detection is essential for trajectory summarization to be useful for debugging and agent improvement. This case shows both models can identify incomplete task execution.
- **Finding:** Both models accurately capture error-recovery patterns in successful trajectories.
  - Evidence: For the UI-TARS trajectory, both models document the accidental text box move, the Ctrl+Z undo, the Insert menu false start, and the correct View > Notes navigation. All judge scores are 5/5 for coverage and factuality.
  - Importance: Error-recovery sequences are procedurally important for understanding agent behavior and robustness. Preserving these details distinguishes informative summaries from superficial ones.
- **Finding:** This paired case demonstrates that both models maintain clear differentiation between failed and successful trajectories performing the same task.
  - Evidence: The doubao summaries end with explicit statements about incompleteness, while the UI-TARS summaries describe the full workflow through to saving and DONE. No model conflates or smooths over the outcome difference.
  - Importance: For paired trajectory analysis, preserving outcome differences is critical. This case provides evidence that current models handle this well for clear-cut success/failure contrasts.
- **Finding:** Automatic metrics (ROUGE-L, BERTScore) show notable variation despite identical perfect judge scores.
  - Evidence: For the doubao trajectory, GPT-5.5 gets ROUGE-L 0.42 vs Claude's 0.35; for UI-TARS, GPT-5.5 gets ROUGE-L 0.51 vs Claude's 0.42. Yet both receive identical judge scores of 5 across all dimensions.
  - Importance: This highlights the limitation of surface-level automatic metrics for evaluating trajectory summaries, as stylistic and structural differences (e.g., numbered lists vs. prose) affect ROUGE/BERTScore without reflecting quality differences.

## 936321ce-5236-426a-9a20-e0e3c5dc536f

- Domain: `libreoffice_writer`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

This paired case demonstrates that both evaluated models can reliably preserve the success/failure distinction even when trajectories share nearly identical procedural steps, accurately localizing failure to a specific missing action (not clicking OK) rather than overgeneralizing. However, the case also reveals that reference-based metrics like ROUGE-L diverge substantially between models despite identical perfect judge scores, suggesting these metrics may be unreliable indicators of trajectory summary quality.

### Trajectory contrast

The successful trajectory (doubao) initially failed to open the Text to Table dialog because no text was selected, then corrected by selecting text first and re-navigating the menu. The failed trajectory (UI-TARS) correctly selected text first and opened the dialog with proper settings, but terminated with FAIL before clicking OK to confirm the conversion.

The successful agent demonstrated error recovery (learning that text must be selected first), while the failed agent followed the correct procedure but stopped prematurely before the final confirmation step. The failure was not due to a wrong approach but to incomplete execution.

### Main qualitative findings

- **Finding:** Both evaluated models perfectly preserved the success/failure distinction across paired trajectories, receiving maximum judge scores on all dimensions for both summaries.
  - Evidence: All four summaries received Coverage=5, Factuality=5, Temporal order=5, Specificity=5, Procedural usefulness=5, with no omissions or hallucinations flagged by judges.
  - Importance: This demonstrates that current strong models can reliably distinguish and communicate success vs. failure outcomes in trajectory summarization, even when the procedural steps are very similar between the two trajectories.
- **Finding:** The case illustrates that failure can occur at the very last step of an otherwise correct procedure, and both models captured this nuance rather than characterizing the failure trajectory as broadly incorrect.
  - Evidence: Both models noted that the UI-TARS agent followed the correct procedure (select text, navigate menus, configure separator) but failed specifically because it did not click OK to confirm. Neither model overgeneralized the failure.
  - Importance: Accurate failure localization in summaries is critical for downstream use cases like debugging agent behavior or training improved agents.
- **Finding:** The error-recovery pattern in the successful trajectory was well-preserved by both models, maintaining the causal narrative of why the initial attempt failed and how the agent corrected course.
  - Evidence: Both GPT-5.5 and Claude Sonnet 4.6 explicitly described the initial failed attempts due to unselected text, the correction step of selecting text, and the subsequent successful attempt.
  - Importance: Preserving error-recovery narratives is important because they reveal agent reasoning capabilities and adaptation strategies, which are lost if only the final successful procedure is summarized.
- **Finding:** Despite perfect judge scores, the automatic reference metrics (ROUGE-L, BERTScore) show moderate variation across models and trajectories, suggesting these metrics may not fully capture summary quality for agent trajectories.
  - Evidence: GPT-5.5 achieved ROUGE-L of 0.533 and 0.519 for the two trajectories, while Claude achieved 0.419 and 0.434, yet both received identical perfect judge scores.
  - Importance: This highlights a potential disconnect between reference-based automatic metrics and human-judged quality, relevant for evaluation methodology in the paper.

## 47f7c0ce-a5fb-4100-a5e6-65cd0e7429e5

- Domain: `multi_apps`
- Pair outcome: `both_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

In this both-failure paired case, neither evaluated model explicitly flagged task failure, instead framing agent termination as task completion. While both models accurately preserved the key procedural difference between trajectories (VLC snapshot vs. PrintScreen fallback), they diverged on capturing behavioral anomalies: Claude achieved higher coverage by including retry behaviors but introduced subtle causal misinterpretations, while GPT-5.5 maintained factual accuracy at the cost of omitting notable agent behaviors.

### Trajectory contrast

Both trajectories fail the task but follow substantially different procedures. The doubao agent uses VLC's built-in 'Take Snapshot' menu to capture the frame and then enters a repetitive loop in LibreOffice Impress when trying to set the background. The UI-TARS agent struggles with seeking to 00:08 (overshooting/undershooting multiple times), fails twice to capture a screenshot via Shift+S, resorts to the system PrintScreen tool to capture the full screen instead of just the video frame, and then redundantly clicks 'Insert Image...' a second time after incorrectly concluding the background was not set.

Both agents fail (success_raw = 0.0). The doubao agent likely fails because its repetitive loop behavior may not have properly applied the background, while the UI-TARS agent likely fails because it captured a full-screen screenshot (including VLC UI chrome) rather than just the video frame, and may have had issues with the background application as well.

### Main qualitative findings

- **Finding:** Both models fail to explicitly flag task failure despite both trajectories having success_raw = 0.0.
  - Evidence: Neither GPT-5.5 nor Claude's summaries for either trajectory mention that the task was ultimately unsuccessful. Both frame the final actions as completing the task (e.g., 'clicked Open to apply it as the slide background,' 'the agent issued DONE').
  - Importance: For trajectory summarization to be useful for debugging and analysis, summaries should ideally note when a task fails, or at minimum avoid implying success when the outcome is failure.
- **Finding:** Claude achieves higher coverage scores but introduces subtle interpretive errors when explaining agent behavior.
  - Evidence: Claude scores 5/5 coverage on both trajectories vs. GPT-5.5's 4/5 on both. However, Claude's UI-TARS summary claims the second Insert Image attempt succeeded, which the gold summary contradicts ('incorrectly concludes that the background was not set').
  - Importance: Higher coverage can come at the cost of accuracy when models fill in causal explanations for observed behaviors. This trade-off between completeness and factual precision is important for summarization quality.
- **Finding:** The procedural difference in frame capture method (VLC snapshot vs. full-screen PrintScreen) is well-preserved by both models across the paired trajectories.
  - Evidence: Both models clearly distinguish that doubao used VLC's 'Take Snapshot' menu while UI-TARS failed with Shift+S and fell back to PrintScreen. This is the most important procedural difference between the trajectories.
  - Importance: Preserving method-level differences is critical for understanding why different agents succeed or fail at the same task, and both models handle this well.
- **Finding:** GPT-5.5 achieves notably higher ROUGE-L and BERTScore for the doubao trajectory but lower judge scores than Claude, highlighting metric-judgment divergence.
  - Evidence: GPT-5.5 doubao: ROUGE-L 0.589, BERTScore 0.585, Coverage 4. Claude doubao: ROUGE-L 0.366, BERTScore 0.245, Coverage 5. The automatic metrics favor GPT-5.5 while the judge favors Claude.
  - Importance: This demonstrates that automatic metrics may reward surface-level lexical overlap with gold summaries while missing coverage and structural quality that human judges value.

## 7b1e1ff9-bb85-49be-b01d-d6424be18cd0

- Domain: `thunderbird`
- Pair outcome: `mixed_success_failure`
- Recommended paper use: `medium`

### Paper-ready takeaway

In this mixed success/failure pair, both evaluated models accurately captured the key procedural misstep (an erroneous Open Directory click) that distinguished the failing trajectory, but neither explicitly flagged the task failure outcome, illustrating a systematic gap where trajectory summaries describe actions without connecting them to task success or failure — a limitation that reduces their diagnostic utility for agent debugging.

### Trajectory contrast

Both agents follow a similar path (hamburger menu → Tools → Help → Troubleshooting Information → about:profiles), but the failing agent (doubao) makes an additional mistake by clicking 'Open Directory' which opens a file manager, requires closing it, and then clicks the about:profiles link three times redundantly. The successful agent (UI-TARS) navigates more efficiently in 8 steps without the file manager detour.

The task outcome difference (fail vs. success) is somewhat surprising given that both agents ultimately reach the about:profiles page. The failing agent's extra misstep (opening the file manager) and redundant clicking may have caused a state issue, or the evaluation may have detected the file manager window or other side effects. The successful agent completed the task cleanly and concisely.

### Main qualitative findings

- **Finding:** Both models accurately capture the key procedural difference (Open Directory mistake) but neither explicitly flags the task failure outcome.
  - Evidence: Both summaries of the failing trajectory describe the file manager detour and repeated clicking but end with the agent issuing DONE without noting the task was unsuccessful. The gold summary also does not explicitly state failure, suggesting this may be an inherent limitation of trajectory-only summarization.
  - Importance: For trajectory summarization to be maximally useful for debugging and analysis, summaries should ideally indicate whether the task succeeded or failed, not just describe the steps taken.
- **Finding:** Claude Sonnet 4.6 achieves higher specificity scores consistently, particularly through step-number references and exact counts.
  - Evidence: Claude received 5/5 specificity on both trajectories while GPT-5.5 received 4/5 on both. The judge noted GPT-5.5's lack of specific click counts and UI element locations as minor losses of specificity.
  - Importance: In mixed success/failure pairs, higher specificity helps readers distinguish between trajectories that follow similar paths but diverge at critical moments.
- **Finding:** Despite the success/failure difference, both models produce structurally similar summaries for both trajectories, differing mainly in the inclusion of the error episode.
  - Evidence: The successful trajectory summaries from both models are nearly identical in content and structure. The failing trajectory summaries add the Open Directory detour and repeated clicks but otherwise mirror the successful trajectory's narrative arc.
  - Importance: This suggests that when trajectories share a common procedural skeleton, models can reliably identify and report the divergent episodes, which is encouraging for comparative trajectory analysis.
- **Finding:** The case illustrates that procedural missteps alone may not explain task failure, and summaries that omit outcome information leave the reader without crucial context.
  - Evidence: The failing agent appears to reach about:profiles (the correct page) yet still fails. Neither model's summary explains why the task failed despite apparently reaching the goal state. Possible explanations (e.g., triple-clicking caused navigation issues, file manager window interference) are not explored.
  - Importance: This highlights a gap in current trajectory summarization: models describe what happened but not why it mattered for task success, limiting the diagnostic utility of summaries.
