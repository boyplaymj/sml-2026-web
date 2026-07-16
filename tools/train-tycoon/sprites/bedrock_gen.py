#!/usr/bin/env python3
# Bedrock Stability SD3.5 生圖(us-west-2)。用法: python3 bedrock_gen.py "<prompt>" <out.png> [aspect]
import sys, json, base64, boto3

prompt = sys.argv[1]
out = sys.argv[2]
aspect = sys.argv[3] if len(sys.argv) > 3 else "1:1"
cli = boto3.client("bedrock-runtime", region_name="us-west-2")
body = {"prompt": prompt, "mode": "text-to-image", "aspect_ratio": aspect, "output_format": "png"}
resp = cli.invoke_model(modelId="stability.sd3-5-large-v1:0", body=json.dumps(body))
data = json.loads(resp["body"].read())
b64 = data.get("images", [None])[0] or data.get("image")
if not b64:
    raise SystemExit("no image in response: " + json.dumps(data)[:300])
open(out, "wb").write(base64.b64decode(b64))
print("ok", out)
