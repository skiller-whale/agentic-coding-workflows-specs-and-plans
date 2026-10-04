---
name: checkpoint
description: Reset the city exercise to a known-good checkpoint. Only for the learner to run, as /checkpoint.
disable-model-invocation: true
---

The learner wants to reset their city to a checkpoint.

1. Ask which checkpoint they want, with the AskUserQuestion tool. Say that it replaces their code, tests and specs. Offer exactly these three options:
   - **The start**: the city map as it was at the beginning, with no features.
   - **Deliveries working**: one car driving around at random, delivery jobs appearing on buildings, and the car collecting and delivering packages (features 1 to 3).
   - **A busy city**: five cars earning money for deliveries, with traffic lights at some junctions (features 1 to 6).
2. Run the restore script with the matching name, `start`, `deliveries` or `busy`:

   ```shell
   bash .session/checkpoint.sh deliveries
   ```

3. Tell the learner the checkpoint is loaded and that the City app restarts by itself. Then recommend, in your own words, that they run `/clear` before they carry on, so their next change starts with a fresh context.

Don't read, summarise or explain the restored code or specs unless the learner asks about them afterwards.
