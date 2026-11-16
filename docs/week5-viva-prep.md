# Week 5: Viva Preparation

Every member must be able to answer every question below. Numbers in **[brackets]** come from Section 8 of `docs/final-report.md`; read them from there on the day.

---

## 1. Talk plan (10 minutes + questions)

| Time | Slide / action | Speaker | Key line |
|---|---|---|---|
| 0:00 | Title, team, one-sentence claim | Research lead | "Moving to the cloud is not enough; the architecture is what makes a system survive failure." |
| 0:45 | The 2008 incident and root causes | Research lead | One database corruption, three days without shipping DVDs [R3] |
| 1:45 | Migration journey 2008–2016, why seven years | Research lead | Netflix refactored, it did not rehost |
| 2:45 | Before/after architecture (Figure 1) | Cloud engineer | Each layer removes one single point of failure |
| 3:45 | Chaos Monkey → Gorilla → Kong → FIT → ChAP | Testing engineer | Widen the blast radius, then automate it |
| 4:45 | Our experiment: stages, hypotheses fixed in advance (Figure 2) | Testing engineer | Same app, same failure, different architecture |
| 5:45 | **Live demo** (`bash demo/demo.sh`, steps 1–5) | Testing engineer | Breaker on: 200 + fallback. Breaker off: 502 |
| 7:45 | Results table (H1–H6) and charts | Analysis lead | What we measured, what we could not |
| 8:45 | Cost model: break-even and Open Connect | Analysis lead | Cloud for the brain, owned hardware for the bytes |
| 9:30 | Limitations and conclusion | Analysis lead | On AWS: one VM 37.5%, refactored 98.9–99.5%; scale-out not tested |

Fallback if the live demo fails: play the recorded video (Section 3) and keep going. Do not debug live.

---

## 2. Likely questions and model answers

### The case

**Q1. Why did Netflix leave its data center?**
After the August 2008 database corruption stopped DVD shipping for three days [R3]. The root problem was single points of failure (one site, one vertically scaled database, a monolith) plus slow up-front capacity planning, just as streaming demand was about to grow fast and unpredictably. Netflix also did not want to spend engineers on "undifferentiated heavy lifting" [R1].

**Q2. Why AWS, and why not just build a second data center?**
A second data center would have reduced site risk but kept capital cost, months-long hardware planning and the monolith. AWS gave capacity "almost instantly" and the broadest set of services at the time [R1, R3]. The motive was elasticity and focus, not lower unit cost.

**Q3. Why did the migration take seven years?**
Netflix chose the "cloud native approach": it rebuilt almost everything as microservices rather than moving the monolith as it was [R3]. Data had to move from a relational database to distributed stores with different consistency rules, and most tooling (discovery, deployment, monitoring) had to be built because it did not exist in 2009. The service also kept running for a fast-growing customer base. Billing and customer data moved last, because they were the riskiest.

**Q4. In the "6 Rs" of migration, where do S1 and S2 sit?**
S1 is **rehost** (lift-and-shift: same container on one VM). S2 is **refactor/re-architect** (split into services, ASG, managed database). Moving the database to RDS alone would be **replatform**.

**Q5. Why microservices and NoSQL?**
Microservices let one feature fail or be deployed without taking down the rest, and let teams release independently. Cassandra replicates across AZs and regions and keeps accepting writes during node failures (Dynamo-style availability over strict consistency [R22, R23]). Trade-off: much higher operational complexity.

**Q6. What is Chaos Monkey, and how is it different from Chaos Gorilla and Chaos Kong?**
Chaos Monkey terminates random instances in an Auto Scaling Group during working hours. Chaos Gorilla simulates losing a whole Availability Zone. Chaos Kong evacuates a whole AWS region. Each one widens the blast radius. FIT and ChAP later narrowed it again: inject failure into a small, chosen slice of real traffic and compare it with a control group, with an automatic stop [R4, R7].

**Q7. What are the principles of chaos engineering?**
Define a steady state (Netflix: stream starts per second; ours: % of home-page requests that return 200 within 1 s), hypothesise it continues, inject real-world events, try to disprove the hypothesis, and minimise the blast radius [R8].

**Q8. Is there evidence that chaos engineering worked for Netflix?**
On Christmas Eve 2012 an AWS ELB failure in us-east-1 disrupted Netflix streaming in the Americas for about 20 hours. After Netflix built multi-region failover and ran regional drills, the September 2015 DynamoDB disruption in the same region hit many AWS customers, and Netflix reported no significant impact [R26]. Caveat: Netflix did not publicly credit one specific tool.

**Q9. Is Hystrix still used?**
It has been in maintenance mode since 2018. Netflix moved to adaptive concurrency limits and points new projects to resilience4j [R10]. The pattern (timeout + circuit breaker + fallback) is the same; we used Python `pybreaker`.

**Q10. Is the cloud cheaper than on-prem?**
Not always. Netflix says cloud cost per streaming start ended up a "fraction" of the data center cost [R3], but it runs its own CDN, Open Connect, because at huge, steady video volume owning is cheaper [R5]. Our cost model shows the same pattern: a control-plane break-even of about **240–308 average vCPU** and a CDN break-even of about **187 TB/month** (Estimates).

### Our experiment

**Q11. What did you build?**
A movie-catalogue app (Flask, Gunicorn, Postgres, Docker) in four stages: S0 monolith on a laptop; S1 the same container on one EC2 instance; S2 three services (catalogue, recommendations, auth) in an ASG across 2 AZs behind an ALB with RDS; plus chaos scripts, a load generator and a cost model. S1 and S2 are fully written in Terraform (`infra/`).

**Q12. Why did you fix the hypotheses and thresholds before testing?**
So results cannot be bent to fit afterwards. The 99% / 2× / 500 ms thresholds act as a simple SLO [R18].

**Q13. How does your circuit breaker work?**
The catalogue calls recommendations over HTTP with a 250 ms timeout. After 5 failures `pybreaker` opens and stops calling for 10 s, returning a generic popular list (`X-Recs-Source: fallback`). After 10 s it half-opens and tries one real call. With `BREAKER=off`, the call has a 5 s timeout and no fallback, so the home page returns 502.

**Q14. What did E4 (recommendations down) show?**
With the breaker, home-page availability stayed at **100.0%** in all three runs, with **40.5%** of home pages served from the fallback (the fault lasted 120 of 300 s). Without it, availability fell to **59.6%** (range 59.3–60.6%) and the home page returned 502 for the whole 120 s. H5 **accepted**. The same failure gave a different result depending only on the design.

**Q15. What did E3 (300 ms latency) show? Why is slow worse than down?**
A slow dependency holds worker threads. Without a short timeout, every home page waits for recommendations, so latency rises for everyone and threads can run out. With the 250 ms timeout the breaker treats slow like down and falls back. Without the breaker, home-page p95 went to **803 ms** and throughput fell **30%** (95 → 67 req/s); with it, p95 stayed at **21 ms** and 38% of pages used the fallback.

**Q16. What happened when you ran S1 and S2 on AWS?**
On 14 November 2026, in us-east-1, built with Terraform and destroyed afterwards. S1: stopping the only instance gave **37.5%** availability and a **537 s** outage; even after the restart, clients stayed down because the instance came back with a **new public IP**. S2: three random kills gave **98.92%** (longest gap 5 s); losing all of us-east-1a gave **99.47%**. The ASG launched each replacement within 2 s and was back to full capacity in **114–176 s**, with no human action. H1 and H3 accepted, H2 partly (E1 missed 99% by 0.08 points because the ALB needs ~20 s to detect a dead target). H4 partly: under a heavy ramp the ASG scaled 2 → 4 on its own and throughput rose 305 → 370 req/s, but our one laptop saturated at ~300 req/s (all errors were client-side timeouts), so the latency criterion could not be judged. We lowered the CPU target from 50% to 30% during that run and say so. Bonus finding: an overloaded instance failed its health check, and its first replacement was refused by the new account's vCPU quota; the ASG retried a minute later. Evidence: `results/aws-logs/` (Terraform logs, AWS's own ASG activity history) and the instance IDs in every `requests.csv`.

**Q17. How does an Auto Scaling Group recover a terminated instance, and what sets recovery time?**
The ASG notices that running capacity is below the desired count (from the EC2 health check, or the ALB health check if ELB health checks are enabled) and launches a replacement from the launch template. Recovery time = detection + instance boot + user data (Docker pull, container start) + health check grace period (ours: 120 s) + the ALB needing a number of healthy checks in a row. Expect a few minutes; Netflix shortened this with pre-baked AMIs.

**Q18. Why min 2 instances across 2 AZs?**
With one instance, any kill is an outage (that is S1). Two instances in different AZs mean one kill or one AZ loss leaves half the capacity serving while the ASG replaces the rest.

**Q19. How did you make sure the chaos script couldn't damage anything else?**
It only targets instances tagged `project=mini-netflix`, refuses to run if the filter matches more than 4 instances, has `--dry-run`, and logs every action to `events.csv`. Everything ran in our own account and region with a budget alert.

**Q20. Why your own load generator instead of k6?**
So every single request is logged with status, latency, the serving instance and whether the fallback was used. That lets us compute availability per second and time-to-recover exactly from raw CSVs.

**Q21. How reliable are your numbers?**
E0 and E4 have three runs each (median and range reported); E3 and E5 one each. Local-S2 runs the load generator on the same laptop as the services, so absolute latency is only comparable within a stage. The first S0 E5 run was cut off when the laptop went to sleep; we discarded it and re-ran.

**Q22. What would change at Netflix's scale?**
Effects we cannot see with 3 services: retry storms, thundering herds when a breaker closes, dependency chains dozens deep, cross-region replication lag, and the need for statistical, production-traffic experiments (ChAP) rather than our simple before/after.

**Q23. What would you do with more time or budget?**
Repeat each AWS run three times, drive E5 from a load generator on EC2 in the same region so the latency criterion can be judged, compare the boto3 Chaos Monkey with AWS FIS, try ECS Fargate for faster scale-out, and add a second region for a Chaos Kong-style failover (Idea C).

**Q24. What is the main lesson of the project?**
Rehosting moves the problem; refactoring removes it. Then you have to prove the redesign works by breaking it on purpose.

---

## 3. Recorded backup demo

Record it a day before the viva, on the machine you will present from.

1. Close other apps; set the terminal font to at least 16 pt.
2. Start recording (Windows: **Win + Alt + R** with Xbox Game Bar, or OBS).
3. Run `bash demo/demo.sh` and narrate each step (about 4 minutes).
4. Also show `results/local-s2/e4-breaker-on/run1/timeline.png` next to `results/local-s2/e4-breaker-off/run1/timeline.png`.
5. Save as `demo/backup-demo.mp4`. Do **not** commit it if it is larger than about 50 MB; keep it on a USB stick and in Google Drive.

## 4. Day-before checklist

- [ ] Docker Desktop starts; `bash demo/demo.sh` runs end to end
- [ ] Images already built (step 1 must not need to download from Docker Hub)
- [ ] Slides and final report PDF on the laptop and on a USB stick
- [ ] Backup video plays offline
- [ ] Everyone has read Sections 8 and 9 of the final report and can quote the H1–H6 table
- [ ] All `[name]` and `[bracketed]` placeholders filled in
