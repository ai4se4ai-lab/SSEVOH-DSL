----------------------------- MODULE Lifecycle -----------------------------
EXTENDS Naturals, Integers
CONSTANTS Authorized, Evidence, MaxEpoch
VARIABLES phase, epoch, approved, withdrawn, active, certified
vars == <<phase, epoch, approved, withdrawn, active, certified>>
Init == /\ phase = "PROPOSED" /\ epoch = 0 /\ approved = -1
        /\ withdrawn = FALSE /\ active = FALSE /\ certified = -1
Analyse == /\ phase = "PROPOSED" /\ phase' = "ANALYSED"
           /\ UNCHANGED <<epoch, approved, withdrawn, active, certified>>
Verify == /\ phase = "ANALYSED" /\ Authorized /\ phase' = "VERIFIED"
          /\ UNCHANGED <<epoch, approved, withdrawn, active, certified>>
Approve == /\ phase = "VERIFIED" /\ Evidence /\ phase' = "APPROVED"
           /\ approved' = epoch /\ UNCHANGED <<epoch, withdrawn, active, certified>>
Deploy == /\ phase = "APPROVED" /\ approved = epoch /\ ~withdrawn
          /\ phase' = "DEPLOYED" /\ active' = TRUE /\ certified' = approved
          /\ UNCHANGED <<epoch, approved, withdrawn>>
Change == /\ epoch < MaxEpoch /\ epoch' = epoch + 1 /\ active' = FALSE
          /\ UNCHANGED <<phase, approved, withdrawn, certified>>
Withdraw == /\ epoch < MaxEpoch /\ epoch' = epoch + 1 /\ withdrawn' = TRUE
            /\ active' = FALSE /\ UNCHANGED <<phase, approved, certified>>
Recover == /\ withdrawn /\ phase' = "REJECTED" /\ active' = FALSE
           /\ certified' = epoch /\ UNCHANGED <<epoch, approved, withdrawn>>
Reject == /\ phase \notin {"DEPLOYED", "REJECTED"} /\ phase' = "REJECTED"
          /\ UNCHANGED <<epoch, approved, withdrawn, active, certified>>
Next == Analyse \/ Verify \/ Approve \/ Deploy \/ Change \/ Withdraw \/ Recover \/ Reject
Safety == active => (Authorized /\ Evidence /\ ~withdrawn /\ certified = epoch)
Spec == Init /\ [][Next]_vars
=============================================================================
