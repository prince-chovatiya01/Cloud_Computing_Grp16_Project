# IT457 Cloud Computing Case Study: Netflix's AWS Migration and Chaos Engineering

**Topic:** Netflix → AWS migration, Chaos Monkey, and resilience\
**Theme match:** Migration and Transformation (primary), Scalability
(secondary)

------------------------------------------------------------------------

## 1. Case Study Summary (Week 1 Material)

  -----------------------------------------------------------------------
  Item                                Key points
  ----------------------------------- -----------------------------------
  **Problem**                         In August 2008, a major database
                                      corruption in Netflix's own data
                                      center stopped DVD shipping for
                                      about three days. Netflix decided
                                      that a vertically scaled,
                                      single-point-of-failure data center
                                      was too risky for a fast-growing
                                      streaming business.

  **Decision**                        Move to AWS and rebuild as
                                      distributed microservices. The
                                      migration took about seven years
                                      and finished around January 2016,
                                      when the last data-center pieces
                                      (billing) were shut down.

  **Architecture changes**            Monolith → hundreds of
                                      microservices; Oracle → Cassandra
                                      (NoSQL) and later DynamoDB;
                                      services on EC2 Auto Scaling Groups
                                      behind ELB; S3 for storage;
                                      multi-region deployment (US-East,
                                      US-West, EU); Open Connect
                                      (Netflix's own CDN) for video
                                      delivery.

  **Resilience practices**            Chaos Monkey (2010--11, kills
                                      random instances), followed by the
                                      Simian Army (Latency Monkey, Chaos
                                      Gorilla for an Availability Zone,
                                      and Chaos Kong for a whole region),
                                      and later ChAP (Chaos Automation
                                      Platform). Netflix also used
                                      Hystrix circuit breakers and
                                      regional failover drills.

  **Outcomes**                        Higher availability, elastic
                                      scaling, and global expansion.
                                      Engineers design for failure.
                                      Netflix open-sourced much of its
                                      stack, including Eureka, Hystrix,
                                      Zuul, and Chaos Monkey.

  **Cost angle**                      Netflix argued that AWS provided
                                      elasticity and reduced the need for
                                      large capital purchases. Exact
                                      savings are not publicly
                                      documented, so this project will
                                      model costs independently.
  -----------------------------------------------------------------------

### Primary Sources to Cite

-   Netflix Tech Blog: "Four Reasons We Choose Amazon's Cloud as Our
    Computing Platform" (2010).
-   Netflix Tech Blog: "Completing the Netflix Cloud Migration"
    (February 2016).
-   Netflix Tech Blog: "The Netflix Simian Army" (2011) and "Chaos
    Engineering Upgraded" (ChAP).
-   Netflix Chaos Monkey GitHub repository (`Netflix/chaosmonkey`).
-   AWS case study: Netflix on AWS; AWS re:Invent talks on Netflix
    architecture.
-   Book: *Chaos Engineering* (Rosenthal, Jones et al., O'Reilly) and
    principlesofchaos.org.
-   Netflix investor letters or 10-K filings (for scale and cost
    context).

------------------------------------------------------------------------

## 2. Project Ideas (Pick One)

### Idea A: "Mini-Netflix" --- Migrate, Then Break It on Purpose

Build a small monolithic application (for example, a movie catalogue
with a database) running in local Docker.

1.  Lift-and-shift it to one EC2 VM (the "2008 to early AWS" stage).
2.  Refactor it into 2--3 services (catalogue, recommendations, and
    authentication) behind an Application Load Balancer (ALB) with an
    Auto Scaling Group, and move the database to a managed service (RDS
    or DynamoDB).
3.  Run a Chaos Monkey-style script that randomly terminates instances,
    and measure availability, latency, and recovery time with k6 or
    Locust.
4.  Document effort and cost at each stage.

**Covers:** The migration exercise, scalability exercise, and Chaos
Monkey part of the case.

### Idea B: Chaos Engineering Lab Only

Deploy one autoscaled service. Run experiments: kill one instance, kill
all instances in one Availability Zone, inject latency, and exhaust CPU.
Compare designs with no resilience and with resilience.

**Covers:** Resilience in depth, but is weaker on the migration side of
the topic.

### Idea C: Multi-Region Failover ("Chaos Kong" Simulation)

Deploy the same app in two AWS regions with Route 53 health-check
failover. Simulate a regional outage, then measure failover time and
data loss.

**Covers:** The most advanced resilience concept. It costs more, is
harder to set up, and carries more risk of overruns.

### Idea D: Cost and Repatriation Model --- Netflix On-Prem vs AWS vs GCP

Use the AWS and GCP pricing calculators to model a Netflix-like workload
(storage, compute, and egress) and compare it with an on-premises
estimate.

**Covers:** The cost exercise only. It is safe and cheap, but has no
hands-on build, so the Week 3 "build the core of the exercise"
requirement is weak.

### Idea E: Serverless Re-Architecture of One Netflix Component

Rebuild one piece (for example, a thumbnail or metadata API) with Lambda
and API Gateway. Measure cold start and cost per 1,000 requests versus
EC2.

**Covers:** The serverless exercise. Netflix itself is mostly not
serverless, so the link to the case is weaker.

------------------------------------------------------------------------

## 3. Comparison and Recommendation

  -------------------------------------------------------------------------------
  Criteria     A:             B: Chaos    C:             D: Cost     E:
               Mini-Netflix   lab         Multi-region   model       Serverless
  ------------ -------------- ----------- -------------- ----------- ------------
  Fit to the   Excellent      Good        Good           Weak        Weak
  topic                                                              
  (migration                                                         
  **and**                                                            
  chaos)                                                             

  Hands-on     High           High        High           None        Medium
  build                                                              

  Measurable   All three      Two         Two            Cost only   Two
  results                                                            
  (latency,                                                          
  scaling,                                                           
  cost)                                                              

  Risk and AWS Low--medium    Low         Medium--high   None        Low
  cost                                                               

  Feasible in  Yes            Yes         Tight          Yes         Yes
  3 weeks                                                            

  Viva talking Many           Many        Many           Few         Some
  points                                                             
  -------------------------------------------------------------------------------

### Recommended: Idea A, with a Small Cost Model from Idea D Added

**Why this gets the best marks:**

1.  It matches the whole topic. The migration story (monolith to cloud
    microservices) and Chaos Monkey/resilience are both reproduced at a
    small scale.
2.  It ticks every Week 3 requirement: a built core, latency, scaling
    behaviour, and cost are all measured, along with testing.
3.  It produces strong charts (response time vs. instance count,
    availability during chaos, and recovery time).
4.  The plan is incremental. If time runs out, Stage 1 and Stage 2
    results are still valid; chaos testing adds extra value.
5.  It can stay within the free tier or a few dollars of AWS credit.
6.  It gives a clear viva story: "Netflix did this over seven years; we
    reproduced the journey in miniature and measured it."

------------------------------------------------------------------------

## 4. Detailed Plan for Idea A

### 4.1 Experiment Design

  -----------------------------------------------------------------------
  Stage                   What we build           What we measure
  ----------------------- ----------------------- -----------------------
  **S0: Baseline**        Flask or Node app plus  Local latency with
                          Postgres/SQLite in      k6/Locust
                          local Docker            

  **S1: Lift-and-shift**  Same container on one   Latency, setup effort
                          EC2 instance            (hours), monthly cost
                          (t3.micro/small)        

  **S2: Refactor**        Split into services,    Response time
                          ALB + Auto Scaling      vs. instance count
                          Group (minimum 2,       under load, scale-out
                          maximum 4 instances),   time, cost
                          database moved to RDS   
                          or DynamoDB             

  **S3: Chaos**           Python/boto3 script     Error rate,
                          ("mini Chaos Monkey")   availability
                          that terminates a       percentage, time to
                          random instance every N recover (MTTR), latency
                          minutes; optionally AWS spike
                          Fault Injection Service 

  **S4: Compare**         S1 (single VM) vs. S2   Show that S1 goes down
                          (resilient) under the   and S2 self-heals
                          same chaos              

  **S5: Cost model**      AWS vs. GCP calculator  Monthly cost table and
                          and on-prem estimate    break-even discussion
                          for the same workload   
  -----------------------------------------------------------------------

### 4.2 Metrics and Charts to Produce

-   Response time (p50/p95) vs. number of instances.
-   Requests per second vs. time, with instance-count overlay
    (autoscaling behaviour).
-   Availability and error rate during the chaos run (timeline with kill
    events marked).
-   Mean Time to Recovery (MTTR) for each failure type.
-   Cost per stage and cost per 1,000 requests.
-   Effort table (hours) per migration stage.

### 4.3 Architecture Diagram

Draw the architecture in draw.io for the report.

-   **Before:** Browser → single VM (application + database).
-   **After:** Browser → Route 53 → ALB → Auto Scaling Group (2--4 EC2
    instances across 2 Availability Zones) → RDS/DynamoDB.
-   **Monitoring:** CloudWatch for metrics.
-   **Chaos actor:** Chaos script running externally.

### 4.4 Tools

AWS (EC2, ALB, Auto Scaling, RDS/DynamoDB, CloudWatch, optionally FIS),
Docker, k6 or Locust, Python + boto3, matplotlib for charts, draw.io,
and AWS/GCP pricing calculators.

### 4.5 Cost Control (Important)

-   Set an AWS Budget alert at about \$5 before doing anything else.
-   Use t3.micro or t3.small instances and stop or terminate everything
    after each session.
-   Keep load tests short (5--10 minutes).
-   Check whether the college provides AWS Academy or credits.

------------------------------------------------------------------------

## 5. Timeline (Matches the Course Plan)

  -----------------------------------------------------------------------
  Week                    Tasks                   Deliverable
  ----------------------- ----------------------- -----------------------
  **1**                   Read the primary        One-page summary:
                          sources above and       sources found and
                          extract architecture,   salient points (Section
                          cost, and outcome data. 1 is the starting
                          Choose Idea A.          draft).

  **2**                   Detailed case analysis: 10-page report.
                          before-and-after        
                          architecture diagram,   
                          problem and solution.   
                          Write the exercise plan 
                          (Section 4). Assign     
                          roles.                  

  **3**                   Build S0--S2, run load  Report add-ons with
                          tests, build and run    results.
                          the chaos script        
                          (S3--S4), and cost      
                          model (S5). Save raw    
                          data and screenshots.   

  **4**                   Merge everything,       Final report
                          polish the charts,      submission.
                          proofread, and check    
                          references.             

  **5**                   Rehearse the viva and   Project viva.
                          prepare a demo (or a    
                          recorded backup demo).  
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 6. Team Roles (Adjust to Your Team Size)

  -----------------------------------------------------------------------
  Role                                Responsibilities
  ----------------------------------- -----------------------------------
  **Research lead**                   Sources, case summary, timeline of
                                      the Netflix migration, and
                                      references.

  **Cloud engineer**                  AWS setup, S1 and S2 deployment,
                                      Auto Scaling, and database
                                      migration.

  **Resilience and testing engineer** Chaos script, k6/Locust tests, and
                                      data collection.

  **Analysis and report lead**        Charts, cost model, report
                                      assembly, and viva slides.
  -----------------------------------------------------------------------

Everyone should understand the full pipeline well enough to answer viva
questions.

------------------------------------------------------------------------

## 7. Suggested 10-Page Report Outline

1.  Introduction and objectives (0.5 page).
2.  Netflix case background and problem (1 page).
3.  Migration journey and timeline (1 page).
4.  Architecture before and after, with diagrams (1.5 pages).
5.  Chaos engineering and resilience practices (1.5 pages).
6.  Outcomes, costs, and lessons learned (1 page).
7.  Exercise plan and design (1.5 pages).
8.  Results (added in Week 3): charts and analysis (1.5 pages).
9.  Critical discussion: limits of our simulation and how it differs
    from Netflix scale (0.5 page).
10. Conclusion and references.

------------------------------------------------------------------------

## 8. Likely Viva Questions to Prepare For

-   Why did Netflix leave its own data center, and why did the migration
    take seven years?
-   Why microservices and NoSQL instead of the monolith and Oracle?
-   What is Chaos Monkey, and how is it different from Chaos Gorilla and
    Chaos Kong?
-   How does an Auto Scaling Group recover from a terminated instance,
    and what determines recovery time?
-   What did your results show, and what would change at Netflix's
    scale?
-   Where is the cloud more expensive than on-prem? (Netflix still runs
    its own CDN, Open Connect.)
-   What were the limits of your experiment, and what would you do with
    more time or budget?

------------------------------------------------------------------------

## 9. Tips for Scoring Well

-   Cite primary sources (Netflix Tech Blog, AWS pages), not only
    secondary articles.
-   Mark what is a **public fact** and what is **your own estimate**,
    especially for costs.
-   Show raw measurements and the method, so results are reproducible.
-   Include a "limitations" section. Graders value honest analysis.
-   Keep a running log of effort in hours for the migration comparison.
-   Take screenshots and save scripts and CSVs in this repository as
    evidence for the viva.

------------------------------------------------------------------------

## 10. Suggested Repository Layout

``` text
IT457/Project/
├── README.md
├── docs/          # Week 1 summary, report drafts, diagrams
├── app/           # Mini-Netflix app (Dockerfile, source)
├── infra/         # AWS setup notes or CloudFormation/Terraform
├── chaos/         # chaos_monkey.py
├── loadtest/      # k6 or Locust scripts
├── results/       # raw CSVs, charts, screenshots
└── cost/          # pricing calculator exports and cost table
```
