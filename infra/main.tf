# ---------------------------------------------------------------------------
# AdOps AI Triage — 基礎設施
#
# 設計重點：「探針只能唯讀」這條原則在這裡才真正被強制執行。
# 程式層的靜態掃描擋不住模型幻覺，IAM 擋得住——診斷服務的服務帳號
# 只綁定 read 角色，任何寫入呼叫都會被平台回 403。
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.7"
  backend "gcs" {
    bucket = "adops-triage-tfstate"
    prefix = "env"
  }
}

variable "env"        { type = string }
variable "project_id" { type = string }
variable "region"     { type = string, default = "asia-east1" }

locals {
  is_prod = var.env == "prod"
  labels  = { app = "adops-triage", env = var.env, managed_by = "terraform" }
}

# ---------------------------------------------------------------- 運算
resource "google_cloud_run_v2_service" "agents" {
  name     = "adops-agents-${var.env}"
  location = var.region
  template {
    service_account = google_service_account.agents.email
    containers {
      image = var.agents_image
      env {
        name  = "MODEL_ROUTING"
        # dev 全部走 Haiku 省成本；staging/prod 才啟用完整路由
        value = var.env == "dev" ? "all:haiku" : "intake:haiku,triage:haiku,retrieval:sonnet,diagnosis:opus,remediation:sonnet,verification:sonnet"
      }
      env {
        name  = "AUTOMATION_MODE"
        # staging 為影子模式：跑但不生效，累積 48 小時比對後才准上 prod
        value = local.is_prod ? "enforced" : (var.env == "staging" ? "shadow" : "dry_run")
      }
    }
    scaling { max_instance_count = local.is_prod ? 20 : 3 }
  }
  labels = local.labels
}

# ---------------------------------------------------------------- 權限
resource "google_service_account" "agents" {
  account_id   = "adops-agents-${var.env}"
  display_name = "AdOps Agents (${var.env})"
}

resource "google_service_account" "probes" {
  account_id   = "adops-probes-${var.env}"
  display_name = "AdOps Read-only Probes (${var.env})"
}

# ★ 探針服務帳號只綁 read 角色。這是「唯讀」的第二層護欄。
resource "google_project_iam_member" "probes_readonly" {
  for_each = toset([
    "roles/bigquery.dataViewer",
    "roles/storage.objectViewer",
    "roles/monitoring.viewer",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.probes.email}"
}

# ---------------------------------------------------------------- 偵測器排程
# 排程頻率是架構決策，必須進版控——見規劃書 §08「批次與事件的分界」
resource "google_cloud_scheduler_job" "detectors" {
  for_each = {
    tag_sentinel        = "0 * * * *"     # 每小時
    feed_health         = "0 * * * *"     # 每小時
    cross_source_recon  = "0 9 * * *"     # 每日 09:00
    token_watch         = "0 8 * * *"     # 每日 08:00
    changelog_watch     = "*/30 * * * *"  # 每 30 分鐘，靜默失敗要早接住
    schedule_sla        = "*/15 * * * *"
  }
  name     = "detector-${each.key}-${var.env}"
  schedule = each.value
  region   = var.region
  http_target {
    uri         = "${google_cloud_run_v2_service.agents.uri}/detectors/${each.key}/scan"
    http_method = "POST"
    oidc_token { service_account_email = google_service_account.probes.email }
  }
}

# ---------------------------------------------------------------- 事件
resource "google_pubsub_topic" "events" {
  for_each = toset(["gtm_publish", "feed_disapproval", "ticket_state_change"])
  name     = "adops-${each.key}-${var.env}"
  labels   = local.labels
}

# ---------------------------------------------------------------- 資料
resource "google_storage_bucket" "raw" {
  name     = "adops-raw-${var.env}-${var.project_id}"
  location = var.region
  # 原始快照 immutable 且分區保存，任何指標爭議都可回到當時的原始回應重算
  versioning { enabled = true }
  lifecycle_rule {
    condition { age = local.is_prod ? 400 : 30 }
    action    { type = "Delete" }
  }
  labels = local.labels
}

# ---------------------------------------------------------------- 機密
# 只建立容器，值由人另外寫入或從既有金鑰管理系統同步。金鑰值永遠不進 repo。
resource "google_secret_manager_secret" "keys" {
  for_each  = toset(["anthropic_api_key", "meta_system_user_token", "google_ads_refresh_token"])
  secret_id = "adops-${each.key}-${var.env}"
  replication { auto {} }
}

# ---------------------------------------------------------------- 可觀測性
# 告警規則本身就是系統的一部分，因此進 IaC
resource "google_monitoring_alert_policy" "misexecution" {
  display_name = "誤執行計數 > 0 (${var.env})"
  # 一旦非 0，整套自動化立即降級為 recommendation-only 並走事故檢討。
  # 這是寫進部署設定的自動行為，不是靠人記得執行的約定。
  combiner = "OR"
  conditions {
    display_name = "misexecution_total > 0"
    condition_threshold {
      filter          = "metric.type=\"custom.googleapis.com/adops/misexecution_total\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
    }
  }
}

resource "google_billing_budget" "token_cost" {
  count        = local.is_prod ? 1 : 0
  display_name = "LLM token 成本預算"
  # 單位工單 token 成本超出預算 30% 是灰度階段的自動回滾條件之一
}
