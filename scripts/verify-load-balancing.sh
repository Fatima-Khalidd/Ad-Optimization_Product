#!/usr/bin/env bash
# Section A, task 1 - evidence for the load balancer and the Auto Scaling Group.
#
#   bash scripts/verify-load-balancing.sh ad-optimizer-alb.exampleregion.elasticloadbalancing.amazonaws.com
#
# Needs AWS CLI v2 with credentials for the stack's region (export AWS_DEFAULT_REGION=...).
# Set SKIP_AWS=1 to only do the HTTP distribution check.

set -euo pipefail

ALB_HOST="${1:?usage: verify-load-balancing.sh <alb-dns-name> [requests]}"
REQUESTS="${2:-24}"
SKIP_AWS="${SKIP_AWS:-0}"
HEALTH_PATH="/api/health"

banner() { printf '\n=== %s ===\n' "$1"; }

command -v curl >/dev/null || { echo "curl is required"; exit 1; }

banner "1. The stack answers through the load balancer"
curl -sS -o /dev/null -w 'GET %{http_code}  ttfb=%{time_starttransfer}s  ip=%{remote_ip}\n' \
  "http://$ALB_HOST$HEALTH_PATH"

banner "2. Requests spread over the Auto Scaling instances"
# /api/health reports the serving node (INSTANCE_LABEL, set to the EC2 instance id by the
# launch template), so counting distinct values proves the balancer is fanning out.
declare -A SEEN
for i in $(seq 1 "$REQUESTS"); do
  INSTANCE=$(curl -fsS "http://$ALB_HOST$HEALTH_PATH" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("instance","?"))' 2>/dev/null || echo "error")
  SEEN["$INSTANCE"]=$(( ${SEEN["$INSTANCE"]:-0} + 1 ))
  printf '.%.0s' "$i"
done
echo
printf '\n%s requests distributed as:\n' "$REQUESTS"
for key in "${!SEEN[@]}"; do printf '  %-24s %s\n' "$key" "${SEEN[$key]}"; done
if [ "${#SEEN[@]}" -lt 2 ]; then
  echo "Only one instance answered. Check target health and that the group has min size 2."
else
  echo "Two or more instances answered: load balancing is working."
fi

banner "3. Landing page through the balancer"
curl -sS "http://$ALB_HOST/" | grep -o '<title>[^<]*</title>' || echo "(no <title> found)"

if [ "$SKIP_AWS" != "1" ] && command -v aws >/dev/null 2>&1; then
  banner "4. Target group health"
  TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups \
    --query "TargetGroups[?contains(LoadBalancerArn,'$ALB_HOST')].TargetGroupArn" \
    --output text | head -1)
  echo "target group: $TARGET_GROUP_ARN"
  aws elbv2 describe-target-health --target-group-arn "$TARGET_GROUP_ARN" \
    --query 'TargetHealthDescriptions[].{id:Target.Id,port:Target.Port,state:TargetHealth.State,reason:TargetHealth.Reason}' \
    --output table

  banner "5. Auto Scaling group and its instances"
  # terraform/ outputs the name; override with ASG_NAME=... if you renamed the group.
  ASG_NAME="${ASG_NAME:-ad-optimizer-asg}"
  aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$ASG_NAME" \
    --query 'AutoScalingGroups[0].{name:AutoScalingGroupName,min:MinSize,desired:DesiredCapacity,max:MaxSize,instances:Instances[].InstanceId,az:AvailabilityZone}' \
    --output table

  banner "6. Scaling policies and recent lifecycle activity"
  aws autoscaling describe-scaling-policies --auto-scaling-group-names "$ASG_NAME" \
    --query 'ScalingPolicies[].{name:PolicyName,type:PolicyType,adjustment:ScalingAdjustment}' --output table
  aws autoscaling describe-scaling-activities --auto-scaling-group-names "$ASG_NAME" \
    --max-items 5 --query 'Activities[].{status:StatusCode,cause:Cause,start:StartTime}' --output table
else
  echo
  echo "(AWS CLI not found or SKIP_AWS=1: sections 4-6 skipped. Install aws-cli v2, or run"
  echo " those three commands from the console's equivalent screens for your screenshots.)"
fi

banner "7. Fault tolerance - do this part live"
cat <<'STEPS'
  1. keep this script running in a loop:
       while true; do curl -s http://<alb>/api/health; echo; sleep 1; done
  2. in another terminal, stop one target:
       aws autoscaling terminate-instance-in-auto-scaling-group \
         --instance-id i-XXXX --no-hide-in-auto-scaling-group
  3. the requests keep succeeding: the balancer drops the dead target and the group
     launches a replacement. Screenshot the continuous output plus the lifecycle event.
STEPS
