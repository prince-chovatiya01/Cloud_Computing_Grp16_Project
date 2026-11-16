# AWS Guide: Running S1 and S2 Step by Step

This guide covers the AWS half of the project: deploying **S1** (lift-and-shift, one EC2 instance) and **S2** (ALB + Auto Scaling Group + RDS), breaking them on purpose, collecting the results, and tearing everything down. It tests hypotheses **H1–H4** from Section 7.1 of `docs/final-report.md`, which are currently marked "Not tested".

Follow the steps in order. Every command is run from the **project root** (`d:/IT457/Project`) in **Git Bash**, not PowerShell or cmd.

---

## Contents

0. [Before you start](#0-before-you-start)
1. [Start the session: credentials and variables](#1-start-the-session-credentials-and-variables)
2. [Shared resources: registry and app image](#2-shared-resources-registry-and-app-image)
3. [S1: lift-and-shift on one instance](#3-s1-lift-and-shift-on-one-instance)
4. [S2: load balancer, Auto Scaling Group and RDS](#4-s2-load-balancer-auto-scaling-group-and-rds)
5. [Optional: circuit breaker on AWS (E3/E4)](#5-optional-circuit-breaker-on-aws-e3e4)
6. [Teardown](#6-teardown)
7. [After the session: analysis and report](#7-after-the-session-analysis-and-report)
8. [Troubleshooting](#8-troubleshooting)
9. [Session checklist](#9-session-checklist)

---

## 0. Before you start

### 0.1 What you will run and why

| Stage | Experiment | What happens | Tests | Runs |
|---|---|---|---|---|
| S1 | E0 | 10 min of steady load, no faults | baseline | 1 |
| S1 | **E1** | the only instance is **stopped**; a person must restart it | **H1** | 3 (min 1) |
| S2 | E0 | 10 min of steady load, no faults | baseline | 1 |
| S2 | **E1** | a random instance is **terminated** every 2–3 min | **H2, H3** | 3 |
| S2 | **E2** | every instance in one Availability Zone is terminated | **H2, H3** | 1 |
| S2 | **E5** | load ramps from 5 to 100 virtual users to force scale-out | **H4** | 1 |
| S2 | E3/E4 | latency / recommendations down, breaker on and off | H5 on AWS | optional |

### 0.2 Time and money

| Part | Time |
|---|---|
| Credentials, shared resources, image push | 15 min |
| S1 deploy + runs + teardown | 45–55 min |
| S2 deploy (RDS is slow) | 15 min |
| S2 E0, E1 ×3, E2, E5 + waiting between runs | 90–100 min |
| S2 teardown | 10 min |
| **Core session total** | **≈ 3 h** |
| Optional E3/E4 on AWS | + 60 min |

**Minimum if time is short (≈ 2.5 h):** S1 E1 ×1, S2 E1 ×3, S2 E2 ×1, S2 E5 ×1. That still tests H1–H4.

**Cost:** well under $1 for the whole session (t3.micro instances, one ALB, one db.t3.micro RDS, a few hours each). On AWS Academy it comes out of your lab credit, not a card.

AWS Academy credentials last **about 4 hours**. Start early and don't take a long break with resources running. Clicking **Start Lab** again resets the timer.

### 0.3 One-time tool check

Run these once. All of them must work:

```bash
terraform -version            # v1.5 or newer (installed: v1.16)
aws --version                 # aws-cli/2.x
python --version              # 3.12
docker version                # Docker Desktop must be RUNNING (needed to build the image)
pip install -r requirements-tools.txt
```

Optional but recommended: run the tests and a dry run of the chaos script so you know the Python side works:

```bash
python -m pytest app/tests chaos/test_chaos_monkey.py
```

### 0.4 Golden rules

1. **Never leave resources running after the session.** Every session ends with Section 6.
2. **Don't delete anything in `infra/*/`** during the project. Terraform keeps its state (`terraform.tfstate`) there. Without it, `destroy` can't find what it created. The state is git-ignored on purpose, because it contains the database password.
3. **One stage at a time.** Destroy S1 before running the S2 E3/E4 experiments.
4. If something goes wrong and you are unsure, **destroy first, debug later.**

---

## 1. Start the session: credentials and variables

Do this at the start of **every** session, and again whenever you open a new Git Bash window. Variables don't carry over between windows.

### 1.1 Get AWS credentials (AWS Academy Learner Lab)

1. Open AWS Academy → your course → **Modules → Learner Lab**.
2. Click **Start Lab** and wait until the dot next to "AWS" turns **green** (1–2 min).
3. Click **AWS Details**, then **Show** next to "AWS CLI".
4. Copy the whole block (`[default]`, `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`).
5. Open `C:\Users\ASUS\.aws\credentials` in a text editor, **replace** the existing `[default]` section with what you copied, and save.
6. Make sure the region is us-east-1:

```bash
aws configure set region us-east-1
```

### 1.2 Check the credentials

```bash
aws sts get-caller-identity
```

You should see JSON with `"Account"` and an `"Arn"` that contains `voclabs` or `LabRole`. If you see `InvalidClientTokenId` or `ExpiredToken`, the credentials are old: repeat 1.1.

### 1.3 Set the session variables

Paste this block into Git Bash:

```bash
cd /d/IT457/Project
export AWS_REGION=us-east-1
export MYIP=$(curl -s https://checkip.amazonaws.com)/32
echo "my IP: $MYIP"
```

`MYIP` is used so that **only your laptop** can reach the app. If your network changes (for example you move from Wi-Fi to a phone hotspot), your IP changes too. Then re-run this block and re-run the `terraform apply` of the stage you are on.

---

## 2. Shared resources: registry and app image

Creates the container registry (ECR) the instances pull the app from. On a new account this is done once; later sessions only need 2.3 to reload the variables.

### 2.1 Create the registry

```bash
terraform -chdir=infra/shared init
terraform -chdir=infra/shared apply -var existing_instance_profile=LabInstanceProfile
```

Type `yes` when asked. Expected ending: `Apply complete! Resources: 1 added`.

> **Why `LabInstanceProfile`?** AWS Academy doesn't let you create IAM roles. Its built-in `LabInstanceProfile` already allows the instances to pull from ECR and receive SSM commands.
> **Not on Academy (own AWS account)?** Use `-var budget_email=<your email>` instead. That creates the instance role and a $5 budget alert.

### 2.2 Build and push the app image

Docker Desktop must be running.

```bash
bash infra/build_push.sh
```

The first run takes 2–5 minutes. Expected last line: `pushed <account>.dkr.ecr.us-east-1.amazonaws.com/mini-netflix:latest`.

You only need to push again if you change the code in `app/`.

### 2.3 Load the variables Terraform needs

Terraform reads any `TF_VAR_<name>` environment variable as the value of variable `<name>`. Setting these once means every `apply` and `destroy` below needs no `-var` flags:

```bash
export TF_VAR_image=$(terraform -chdir=infra/shared output -raw ecr_repository_url):latest
export TF_VAR_instance_profile=$(terraform -chdir=infra/shared output -raw instance_profile_name)
export TF_VAR_allowed_cidr=$MYIP
echo "$TF_VAR_image  $TF_VAR_instance_profile  $TF_VAR_allowed_cidr"
```

All three values must be non-empty. **Re-run this block in every new Git Bash window.**

---

## 3. S1: lift-and-shift on one instance

S1 is the same container as the laptop baseline, moved onto **one** EC2 instance in **one** AZ, with nothing to replace it if it dies. The point of S1 is to show that **rehosting doesn't make the app more resilient**.

### 3.1 Deploy

```bash
terraform -chdir=infra/s1 init
time terraform -chdir=infra/s1 apply -auto-approve
```

**Write down the `real` time** printed by `time` (setup effort for the report and `docs/effort-log.md`).

```bash
export S1=$(terraform -chdir=infra/s1 output -raw url)
export S1_ID=$(terraform -chdir=infra/s1 output -raw instance_id)
echo $S1
until curl -sf $S1/health; do echo "waiting..."; sleep 5; done; echo " UP"
```

The first boot takes 1–3 minutes: the instance installs Docker, pulls the image and starts Postgres and the app. When it prints `UP`, open `$S1` in a browser and check that the home page shows movies.

### 3.2 E0: steady load (baseline)

```bash
python chaos/run_experiment.py --stage s1 --exp E0 --run 1 --url $S1 --probe-url $S1
```

This runs for **10 minutes**. When it finishes it prints `results in results/s1/e0/run1`. Open `timeline.png` in that folder: availability should be about 100%.

### 3.3 E1: the only instance dies (H1)

This is the key S1 experiment. The script **stops** the instance 60 seconds into the run. You play the on-call engineer who notices the outage and fixes it by hand.

**Step 1.** Start the run in the background:

```bash
python chaos/run_experiment.py --stage s1 --exp E1 --run 1 --url $S1 --probe-url $S1 &
```

**Step 2.** Watch the terminal. At about 60 s a line with `'action': 'stop'` appears, followed by errors from the load generator.

**Step 3.** Wait about 60 more seconds, as if the alert had just reached you. Then restart the instance by hand and **note the clock time**:

```bash
date +%H:%M:%S; aws ec2 start-instances --instance-ids $S1_ID
```

**Step 4.** Wait for the run to finish (10 minutes in total):

```bash
wait
```

The `timeline.png` should show a long gap of failed requests that only ends **after** your manual restart. That is H1: the service is down until a person acts.

> **Note:** restarting an instance usually gives it a new public IP, so after the restart the load generator may keep failing even though the instance is healthy. That's an honest result of a single-VM design (clients must be told the new address). Write it down in the report. The `watch.csv` file shows the instance state from AWS's side.

**Before the next run**, wait until the instance is running, then pick up its new IP:

```bash
aws ec2 wait instance-running --instance-ids $S1_ID
terraform -chdir=infra/s1 apply -refresh-only -auto-approve
export S1=$(terraform -chdir=infra/s1 output -raw url)
until curl -sf $S1/health; do echo "waiting..."; sleep 5; done; echo " UP at $S1"
```

**Repeat 3.3 with `--run 2` and `--run 3`** if you have time.

### 3.4 Screenshots (S1)

Save to `results/screenshots/`:
- EC2 console showing the instance in **Stopped** state during E1
- The `terraform apply` output with the timing

### 3.5 Tear down S1

```bash
terraform -chdir=infra/s1 destroy -auto-approve
```

Expected: `Destroy complete! Resources: 2 destroyed.` Do this **before** continuing to S2.

---

## 4. S2: load balancer, Auto Scaling Group and RDS

S2 is the refactored design: three services (catalogue, recommendations, auth) on **2–4 instances across 2 AZs** behind an **ALB**, with a managed **RDS Postgres** database. The Auto Scaling Group (ASG) keeps at least 2 instances alive and adds more when average CPU goes above 50%.

### 4.1 Deploy

```bash
terraform -chdir=infra/s2 init
time terraform -chdir=infra/s2 apply -auto-approve
```

This takes **10–15 minutes**, mostly RDS. **Write down the `real` time.** Then:

```bash
export S2=$(terraform -chdir=infra/s2 output -raw url)
export ASG=$(terraform -chdir=infra/s2 output -raw asg_name)
export TG=$(terraform -chdir=infra/s2 output -raw catalogue_target_group)
export W="--asg $ASG --target-group $TG"
echo "$S2  $ASG  $TG"
until curl -sf $S2/health; do echo "waiting..."; sleep 10; done; echo " UP"
```

Open `$S2` in a browser and check the home page.

### 4.2 The "ready" check (use it before EVERY S2 run)

Each S2 run must start from a healthy steady state: **2 instances, both `InService` and `Healthy`**. Define this helper once per Git Bash window:

```bash
asg_status() {
  aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $ASG \
    --query "AutoScalingGroups[0].{desired:DesiredCapacity,instances:Instances[].[InstanceId,AvailabilityZone,LifecycleState,HealthStatus]}" \
    --output json
}
asg_status
```

Ready means `"desired": 2` and two rows with `InService` and `Healthy`. If not, wait a minute and check again. Replacement instances take about 3–5 minutes.

### 4.3 E0: steady load (baseline)

```bash
python chaos/run_experiment.py --stage s2 --exp E0 --run 1 --url $S2 $W
```

10 minutes. Results go to `results/s2/e0/run1/`.

### 4.4 E1: random instance kills (H2, H3)

```bash
asg_status        # must be ready
python chaos/run_experiment.py --stage s2 --exp E1 --run 1 --url $S2 $W
```

10 minutes. After a 60 s steady period, the Chaos Monkey **terminates** one random `mini-netflix` S2 instance, then another every 2–3 minutes. Expect 3–4 kills per run.

What you should see:
- the terminal prints each kill (`'action': 'terminate'`)
- availability stays at or above 99%, because the ALB sends traffic to the surviving instance (**H2**)
- within a few minutes the ASG launches a replacement and capacity returns to 2 with nobody touching anything (**H3**); `watch.csv` records this

While it runs, take the screenshots in 4.8.

Then wait for ready (4.2) and **repeat with `--run 2` and `--run 3`.**

### 4.5 E2: lose an Availability Zone (H2, H3)

First check which AZ has instances (`asg_status` shows the AZ for each). With 2 instances there should be one in `us-east-1a` and one in `us-east-1b`.

```bash
asg_status        # must be ready
python chaos/run_experiment.py --stage s2 --exp E2 --run 1 --url $S2 $W --az us-east-1a
```

This kills **every** instance in `us-east-1a` at once (the Chaos Gorilla idea). The service should keep running from `us-east-1b` while the ASG rebuilds capacity.

### 4.6 E5: load ramp and scale-out (H4)

```bash
asg_status        # must be ready
python chaos/run_experiment.py --stage s2 --exp E5 --run 1 --url $S2 $W --duration 900
```

15 minutes. Load ramps from 5 to 100 virtual users. When average CPU stays above 50%, the ASG should raise the desired count from 2 toward 4.

Check during or after the run:

```bash
asg_status                                           # desired should go above 2
aws autoscaling describe-scaling-activities --auto-scaling-group-name $ASG --max-items 5 \
  --query "Activities[].[StartTime,Description]" --output table
```

**If no scale-out happened** (desired stayed at 2), the load was too light to push CPU past 50%. Run a heavier ramp directly (this saves into a separate folder, `run2`):

```bash
mkdir -p results/s2/e5/run2
python chaos/watch.py --stage s2 $W --duration 930 --out results/s2/e5/run2/watch.csv &
python loadtest/loadgen.py --url $S2 --duration 900 --vus 10 --ramp-to 300 --out results/s2/e5/run2/requests.csv --seed 2
wait
python loadtest/analyze.py results/s2/e5/run2 --label "S2 E5 run 2 (heavier ramp)"
```

**After E5**, put the group back to 2 instances instead of waiting about 15 minutes for scale-in:

```bash
aws autoscaling set-desired-capacity --auto-scaling-group-name $ASG --desired-capacity 2
```

### 4.7 What a good S2 result looks like

| Experiment | Expected outcome |
|---|---|
| E1 | Availability ≥ 99%; short dips at each kill; capacity back to 2 within a few minutes, no human action |
| E2 | A larger dip when half the fleet disappears at once, then recovery from the other AZ |
| E5 | p95 latency stays under 500 ms while the instance count rises above 2 |

If a result **doesn't** match, that's still a valid result: report it honestly (for example "H2 rejected: availability 97.8% because the ALB took 20 s to mark the dead target unhealthy").

### 4.8 Screenshots (S2)

Save to `results/screenshots/` with clear names (for example `s2-e1-targets-unhealthy.png`):
- **EC2 → Target Groups → `mini-netflix-catalogue` → Targets** during a kill: one target `unhealthy` or `draining`
- **EC2 → Auto Scaling Groups → `mini-netflix-s2` → Activity**: "Terminating" and then "Launching a new EC2 instance"
- **CloudWatch → Metrics → EC2 → By Auto Scaling Group → CPUUtilization** during E5
- **EC2 → Auto Scaling Groups → Monitoring** showing in-service instances over time
- The `terraform apply` output with its timing

---

## 5. Optional: circuit breaker on AWS (E3/E4)

The circuit breaker result (H5) is already proven locally, so do this only if you have more than an hour left. **S1 must be destroyed first**: the fault script targets every S2 instance via SSM.

### 5.1 Breaker ON (the default)

```bash
asg_status
python chaos/run_experiment.py --stage s2 --exp E3 --tag breaker-on --run 1 --url $S2 $W   # +300 ms latency
asg_status
python chaos/run_experiment.py --stage s2 --exp E4 --tag breaker-on --run 1 --url $S2 $W   # recommendations stopped
```

If these fail with an SSM error, see Troubleshooting 8.6.

### 5.2 Breaker OFF

Switch the setting and replace the instances so they pick it up (about 5–10 min):

```bash
terraform -chdir=infra/s2 apply -auto-approve -var breaker=off
aws autoscaling start-instance-refresh --auto-scaling-group-name $ASG
aws autoscaling describe-instance-refreshes --auto-scaling-group-name $ASG --query "InstanceRefreshes[0].[Status,PercentageComplete]"
```

Repeat the last command until it says `Successful`. Then:

```bash
asg_status
python chaos/run_experiment.py --stage s2 --exp E3 --tag breaker-off --run 1 --url $S2 $W
asg_status
python chaos/run_experiment.py --stage s2 --exp E4 --tag breaker-off --run 1 --url $S2 $W
```

> **Remember:** any later `terraform apply` on S2 without `-var breaker=off` switches the breaker back on.

### 5.3 AWS Fault Injection Service (FIS)

Skip this on AWS Academy: FIS needs an IAM role that Academy doesn't allow you to create. Mention it in the report as future work. On your own account: `terraform -chdir=infra/s2 apply -var enable_fis=true`, then `aws fis start-experiment --experiment-template-id <id from: terraform -chdir=infra/s2 output fis_templates>` while running `loadtest/loadgen.py` and `chaos/watch.py`.

---

## 6. Teardown

**Do this at the end of every session, even if things went wrong.** If your credentials have expired, refresh them (Section 1.1) first, because `destroy` needs valid credentials.

```bash
terraform -chdir=infra/s2 destroy -auto-approve       # 5-10 min (RDS deletion is slow)
terraform -chdir=infra/s1 destroy -auto-approve       # harmless if already destroyed
```

If you opened a new window, re-run Sections 1.3 and 2.3 first so the `TF_VAR_*` variables are set.

**Check that nothing is left running:**

```bash
aws ec2 describe-instances --filters "Name=tag:project,Values=mini-netflix" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query "Reservations[].Instances[].[InstanceId,State.Name]" --output table
aws rds describe-db-instances --query "DBInstances[].[DBInstanceIdentifier,DBInstanceStatus]" --output table
aws elbv2 describe-load-balancers --query "LoadBalancers[].LoadBalancerName" --output table
```

All three should be empty (or show only `deleting`).

**At the very end of the project** (after the last AWS session), also remove the registry:

```bash
terraform -chdir=infra/shared destroy -var existing_instance_profile=LabInstanceProfile
```

Finally, click **End Lab** in AWS Academy.

---

## 7. After the session: analysis and report

### 7.1 Regenerate the tables and charts

```bash
python loadtest/compare.py        # results/summary_table.md + results/charts/*.png (now with s1 and s2 rows)
python cost/cost_model.py         # cost/cost_table.md, now using the measured S1/S2 throughput
```

Check `results/summary_table.md`: there should be new `s1` and `s2` rows with availability, time to recover and capacity restored.

### 7.2 Update the final report (`docs/final-report.md`)

| Section | What to change |
|---|---|
| 7.2 stage table | S1, S2, S3/S4 status → "Run" |
| 8.1 summary table | Add the S1 and S2 rows from `results/summary_table.md` |
| New 8.x | **S1 E1:** outage length, time for a human to restart, new-IP problem |
| New 8.x | **S2 E1/E2:** availability during kills, time to recover, time until capacity was restored, with a timeline figure |
| 8.5 | Add the S2 E5 scale-out result next to the single-machine curve |
| 8.7 hypotheses | Fill in H1–H4: Accepted / Rejected, with numbers |
| 8.8 | Replace "not run" with what was run, when, and the `terraform apply` times |
| 9, 10 | Delete the "AWS half was not run" limitation; add new limitations you found |
| 11 / effort log | Hours for S1 and S2 in `docs/effort-log.md` |

Also update **Q16** in `docs/week5-viva-prep.md`, then regenerate `docs/final-report.pdf`.

### 7.3 Commit the evidence

```bash
git add results/s1 results/s2 results/screenshots results/summary_table.md results/charts cost/cost_table.md docs/
git commit -m "Week 5: S1 and S2 AWS results"
```

Terraform state files are git-ignored, so they won't be committed (they contain secrets).

---

## 8. Troubleshooting

### 8.1 `InvalidClientTokenId` / `ExpiredToken` / `security token included in the request is invalid`
The Academy credentials have expired. Redo Section 1.1 (Start Lab → AWS Details → copy into `~/.aws/credentials`). Running experiments will have failed; re-run the affected run with the same `--run` number (the folder is overwritten).

### 8.2 `curl $S1/health` or `$S2/health` never returns
- **Your IP changed:** `curl -s https://checkip.amazonaws.com` and compare with `$MYIP`. If different, redo 1.3 and 2.3, then `terraform apply` the stage again.
- **Still booting:** S1 can take 3 min; S2 instances wait for RDS. Give it 5 minutes.
- **Image pull failed:** in the EC2 console, select the instance → **Actions → Monitor and troubleshoot → Get system log** and look for `docker` or `ecr` errors. Usually `infra/build_push.sh` wasn't run, or ran with expired credentials.

### 8.3 `terraform apply` fails with `AccessDenied` / `not authorized to perform iam:CreateRole`
You're on Academy but didn't pass `existing_instance_profile=LabInstanceProfile` to `infra/shared`. Re-run 2.1 with it, then 2.3.

### 8.4 `Error acquiring the state lock`
A previous Terraform command was interrupted. Make sure no other Terraform is running, then:
```bash
terraform -chdir=infra/s2 force-unlock <LOCK_ID shown in the error>
```

### 8.5 Chaos Monkey says "refusing: N instances match" or "no candidates"
- **Too many:** more than 4 instances match the tags. Usually an old stage wasn't destroyed. Run the check in Section 6.
- **None:** the instances are not running yet, or S2 was destroyed. Run `asg_status`.

### 8.6 E3/E4 on AWS fail with an SSM error
The instances must show up as managed by Systems Manager:
```bash
aws ssm describe-instance-information --query "InstanceInformationList[].[InstanceId,PingStatus]" --output table
```
If the list is empty, SSM isn't reaching them (it can take 2–3 minutes after boot). If it stays empty, Academy is blocking it: skip Section 5 and say so in the report, since H5 is already tested locally.

### 8.7 E5 never scales out
CPU didn't stay above 50% long enough. Use the heavier ramp in 4.6. You can also lower the target for one run with `terraform -chdir=infra/s2 apply -auto-approve -var cpu_target=30` (say so in the report).

### 8.8 Lab timer about to run out mid-experiment
Click **Start Lab** again in Academy (it resets the timer) and paste the new credentials. If that's not possible, abandon the run and go straight to teardown (Section 6).

### 8.9 `destroy` hangs on the RDS instance or the security group
RDS deletion takes up to 10 minutes; let it finish. If a security group can't be deleted ("has a dependent object"), wait 2 minutes and run `destroy` again: the ALB's network interfaces are released slowly.

---

## 9. Session checklist

Print this or keep it open.

**Start**
- [ ] Docker Desktop running
- [ ] Lab started, credentials pasted, `aws sts get-caller-identity` works
- [ ] Section 1.3 variables set (`MYIP`)
- [ ] Image pushed (2.2) and `TF_VAR_*` set (2.3)

**S1**
- [ ] Deployed; `terraform apply` time noted
- [ ] E0 run 1
- [ ] E1 run 1 (restart time noted) · run 2 · run 3
- [ ] Screenshots taken
- [ ] S1 destroyed

**S2**
- [ ] Deployed; `terraform apply` time noted
- [ ] E0 run 1
- [ ] E1 run 1 · run 2 · run 3 (ready check before each)
- [ ] E2 run 1
- [ ] E5 run 1 (scale-out seen? if not, heavier ramp) → desired capacity back to 2
- [ ] Optional: E3/E4 breaker on and off
- [ ] Screenshots taken
- [ ] S2 destroyed

**End**
- [ ] Section 6 checks show nothing running
- [ ] `compare.py` and `cost_model.py` re-run
- [ ] Hours written into `docs/effort-log.md`
- [ ] End Lab clicked
