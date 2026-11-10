--------------------------- MODULE Publication ---------------------------
EXTENDS Naturals, Integers
CONSTANTS Authorized, Evidence
VARIABLES phase, epoch, approvalEpoch, approved, stored, published, modified,
          revoked, active, copyGood
vars == <<phase,epoch,approvalEpoch,approved,stored,published,modified,revoked,active,copyGood>>
Init == /\ phase = "IDLE" /\ epoch = 0 /\ approvalEpoch = -1
        /\ approved = FALSE /\ stored = FALSE /\ published = FALSE
        /\ modified = FALSE /\ revoked = FALSE /\ active = FALSE /\ copyGood = FALSE
Prepare == /\ phase = "IDLE" /\ Authorized /\ Evidence /\ epoch = 0 /\ ~revoked
           /\ phase' = "PREPARED" /\ approved' = TRUE /\ approvalEpoch' = epoch
           /\ UNCHANGED <<epoch,stored,published,modified,revoked,active,copyGood>>
Stage == /\ phase = "PREPARED" /\ phase' = "STAGED" /\ stored' = TRUE
         /\ UNCHANGED <<epoch,approvalEpoch,approved,published,modified,revoked,active,copyGood>>
Commit == /\ phase = "STAGED" /\ approved /\ epoch = approvalEpoch /\ epoch = 0
          /\ ~revoked /\ ~modified /\ phase' = "COMMITTED" /\ published' = TRUE
          /\ UNCHANGED <<epoch,approvalEpoch,approved,stored,modified,revoked,active,copyGood>>
Fail == /\ phase \in {"PREPARED","STAGED"} /\ phase' = "FAILED"
        /\ UNCHANGED <<epoch,approvalEpoch,approved,stored,published,modified,revoked,active,copyGood>>
Change == /\ epoch = 0 /\ ~active /\ epoch' = 1
          /\ UNCHANGED <<phase,approvalEpoch,approved,stored,published,modified,revoked,active,copyGood>>
Tamper == /\ stored /\ ~modified /\ ~active /\ modified' = TRUE
          /\ UNCHANGED <<phase,epoch,approvalEpoch,approved,stored,published,revoked,active,copyGood>>
Withdraw == /\ ~revoked /\ ~active /\ revoked' = TRUE
            /\ UNCHANGED <<phase,epoch,approvalEpoch,approved,stored,published,modified,active,copyGood>>
Activate == /\ published /\ approved /\ ~active /\ epoch = 0 /\ ~revoked /\ ~modified
            /\ active' = TRUE /\ copyGood' = ~modified
            /\ UNCHANGED <<phase,epoch,approvalEpoch,approved,stored,published,modified,revoked>>
Finish == /\ active /\ active' = FALSE
          /\ UNCHANGED <<phase,epoch,approvalEpoch,approved,stored,published,modified,revoked,copyGood>>
Next == Prepare \/ Stage \/ Commit \/ Fail \/ Change \/ Tamper \/ Withdraw \/ Activate \/ Finish
Safety == active => (published /\ approved /\ Authorized /\ Evidence /\ ~revoked /\ epoch = 0 /\ copyGood)
Spec == Init /\ [][Next]_vars
=============================================================================
