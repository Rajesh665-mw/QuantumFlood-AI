"""
Shelter Request & Inventory Fulfillment Service
Manages shelter operator resource requests, inventory levels,
demand estimation, and fulfillment audit logs.
"""
import os
import json
import time
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from app.config.settings import DATA_PROCESSED_DIR

logger = logging.getLogger(__name__)

_STORAGE_FILE = DATA_PROCESSED_DIR / "shelter_logistics.json"

# Default seed data for initial bootstrap
_DEFAULT_REQUESTS: List[Dict[str, Any]] = [
    {
        "id": "REQ-001",
        "shelter_id": "FAC-001",
        "shelter_name": "Government Polytechnic College Relief Center",
        "resource_type": "Clean Drinking Water (L)",
        "requested_quantity": 2500,
        "urgency": "HIGH",
        "status": "ALLOCATED",
        "allocated_quantity": 2500,
        "fulfilled_quantity": 2000,
        "notes": "Expected 350 displaced persons; immediate drinking water required.",
        "created_at": "2026-10-14T08:30:00Z",
        "updated_at": "2026-10-14T09:15:00Z",
    },
    {
        "id": "REQ-002",
        "shelter_id": "FAC-002",
        "shelter_name": "Bishop Azariah High School Evacuation Center",
        "resource_type": "Emergency Food Rations (Packs)",
        "requested_quantity": 800,
        "urgency": "CRITICAL",
        "status": "ALLOCATED",
        "allocated_quantity": 800,
        "fulfilled_quantity": 0,
        "notes": "Camp population reached 420; supplies exhausted.",
        "created_at": "2026-10-14T10:00:00Z",
        "updated_at": "2026-10-14T10:45:00Z",
    },
    {
        "id": "REQ-003",
        "shelter_id": "FAC-003",
        "shelter_name": "Andhra Loyola College Emergency Complex",
        "resource_type": "Medical First-Aid Kits",
        "requested_quantity": 50,
        "urgency": "MODERATE",
        "status": "PENDING",
        "allocated_quantity": 0,
        "fulfilled_quantity": 0,
        "notes": "Precautionary medical kits for incoming flood evacuees.",
        "created_at": "2026-10-14T11:20:00Z",
        "updated_at": "2026-10-14T11:20:00Z",
    },
    {
        "id": "REQ-004",
        "shelter_id": "FAC-004",
        "shelter_name": "St. Ann's High School Relief Depot",
        "resource_type": "Blankets & Bedding Sets",
        "requested_quantity": 300,
        "urgency": "HIGH",
        "status": "PENDING",
        "allocated_quantity": 0,
        "fulfilled_quantity": 0,
        "notes": "Night temperature drop anticipated; evacuees wet from transit.",
        "created_at": "2026-10-14T12:05:00Z",
        "updated_at": "2026-10-14T12:05:00Z",
    }
]

_DEFAULT_INVENTORY: Dict[str, Dict[str, Any]] = {
    "Clean Drinking Water (L)": {
        "item": "Clean Drinking Water (L)",
        "unit": "Litres",
        "total_stock": 15000,
        "allocated": 2500,
        "available": 12500,
        "category": "Hydration",
    },
    "Emergency Food Rations (Packs)": {
        "item": "Emergency Food Rations (Packs)",
        "unit": "Packs",
        "total_stock": 5000,
        "allocated": 800,
        "available": 4200,
        "category": "Nutrition",
    },
    "Medical First-Aid Kits": {
        "item": "Medical First-Aid Kits",
        "unit": "Kits",
        "total_stock": 250,
        "allocated": 0,
        "available": 250,
        "category": "Medical",
    },
    "Blankets & Bedding Sets": {
        "item": "Blankets & Bedding Sets",
        "unit": "Sets",
        "total_stock": 2000,
        "allocated": 0,
        "available": 2000,
        "category": "Shelter & Comfort",
    },
    "Mobile Power Generators": {
        "item": "Mobile Power Generators",
        "unit": "Units",
        "total_stock": 35,
        "allocated": 0,
        "available": 35,
        "category": "Utilities",
    },
}

_DEFAULT_AUDIT_LOG: List[Dict[str, Any]] = [
    {
        "timestamp": "2026-10-14T09:15:00Z",
        "action": "APPROVE_AND_ALLOCATE",
        "request_id": "REQ-001",
        "details": "Allocated 2,500 L water to Government Polytechnic College Relief Center.",
        "actor": "Incident Command Officer (Automated/Approved)"
    },
    {
        "timestamp": "2026-10-14T10:45:00Z",
        "action": "ALLOCATE_SUPPLIES",
        "request_id": "REQ-002",
        "details": "Allocated 800 food packs to Bishop Azariah High School based on CRITICAL urgency.",
        "actor": "Resource Coordinator"
    }
]

_shelter_requests: List[Dict[str, Any]] = []
_inventory_stock: Dict[str, Dict[str, Any]] = {}
_audit_log: List[Dict[str, Any]] = []


def _save_to_disk() -> None:
    """Atomically persists shelter requests, inventory stock, and audit log to JSON disk storage."""
    try:
        DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = _STORAGE_FILE.with_suffix(".tmp")
        payload = {
            "requests": _shelter_requests,
            "inventory": _inventory_stock,
            "audit_log": _audit_log,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(temp_file, _STORAGE_FILE)
    except Exception as e:
        logger.warning(f"Failed to persist shelter logistics state to disk: {e}")


def _load_from_disk() -> None:
    """Loads shelter logistics state from disk, or initializes defaults if not present."""
    global _shelter_requests, _inventory_stock, _audit_log
    if _STORAGE_FILE.exists():
        try:
            with open(_STORAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _shelter_requests = data.get("requests", [dict(r) for r in _DEFAULT_REQUESTS])
            _inventory_stock = data.get("inventory", {k: dict(v) for k, v in _DEFAULT_INVENTORY.items()})
            _audit_log = data.get("audit_log", [dict(a) for a in _DEFAULT_AUDIT_LOG])
            return
        except Exception as e:
            logger.warning(f"Failed to load shelter logistics from {_STORAGE_FILE}, using defaults: {e}")

    _shelter_requests = [dict(r) for r in _DEFAULT_REQUESTS]
    _inventory_stock = {k: dict(v) for k, v in _DEFAULT_INVENTORY.items()}
    _audit_log = [dict(a) for a in _DEFAULT_AUDIT_LOG]
    _save_to_disk()


# Initialize state on module load
_load_from_disk()


def reset_shelter_logistics() -> None:
    """Helper to reset logistics state back to default seed for testing or environment reset."""
    global _shelter_requests, _inventory_stock, _audit_log
    _shelter_requests = [dict(r) for r in _DEFAULT_REQUESTS]
    _inventory_stock = {k: dict(v) for k, v in _DEFAULT_INVENTORY.items()}
    _audit_log = [dict(a) for a in _DEFAULT_AUDIT_LOG]
    _save_to_disk()


def list_shelter_requests(shelter_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns all shelter requests, optionally filtered by shelter."""
    if shelter_id:
        return [r for r in _shelter_requests if r["shelter_id"] == shelter_id]
    return list(_shelter_requests)


def create_shelter_request(
    shelter_id: str,
    shelter_name: str,
    resource_type: str,
    requested_quantity: int,
    urgency: str = "MODERATE",
    notes: str = ""
) -> Dict[str, Any]:
    """Creates a new validated resource request from a shelter operator."""
    if not requested_quantity or requested_quantity <= 0:
        raise ValueError("Requested quantity must be greater than zero.")
    if not shelter_name or not shelter_name.strip():
        raise ValueError("Shelter facility name cannot be blank.")

    req_id = f"REQ-{len(_shelter_requests) + 1:03d}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_req = {
        "id": req_id,
        "shelter_id": shelter_id,
        "shelter_name": shelter_name.strip(),
        "resource_type": resource_type,
        "requested_quantity": requested_quantity,
        "urgency": urgency.upper(),
        "status": "PENDING",
        "allocated_quantity": 0,
        "fulfilled_quantity": 0,
        "notes": notes.strip() if notes else "",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    _shelter_requests.append(new_req)
    _audit_log.append({
        "timestamp": now_iso,
        "action": "CREATE_REQUEST",
        "request_id": req_id,
        "details": f"Created request for {requested_quantity} {resource_type} at {shelter_name}.",
        "actor": "Shelter Operator"
    })
    _save_to_disk()
    return new_req


def get_inventory_status() -> List[Dict[str, Any]]:
    """Returns current inventory stock levels and allocations."""
    return list(_inventory_stock.values())


def get_inventory_levels() -> Dict[str, Dict[str, Any]]:
    """Returns dict mapping resource_type to stock details."""
    return dict(_inventory_stock)


def allocate_shelter_request(request_id: str, allocated_qty: int) -> Dict[str, Any]:
    """
    Allocates available inventory to a pending request.
    Prevents allocations exceeding available inventory.
    Provides idempotent protection against repeated identical allocations.
    """
    if allocated_qty <= 0:
        raise ValueError("Allocated quantity must be greater than zero.")

    req = next((r for r in _shelter_requests if r["id"] == request_id), None)
    if not req:
        raise ValueError(f"Request '{request_id}' not found.")

    if req["status"] == "FULFILLED":
        raise ValueError(f"Request '{request_id}' has already been fulfilled and cannot be re-allocated.")

    res_type = req["resource_type"]
    stock = _inventory_stock.get(res_type)
    if not stock:
        raise ValueError(f"Resource type '{res_type}' not tracked in inventory.")

    # Idempotent protection: if already allocated this exact amount, return without double-deduction
    if req["status"] in ["ALLOCATED", "PARTIALLY_ALLOCATED", "FULFILLED"]:
        if req["status"] == "ALLOCATED" and allocated_qty == req["allocated_quantity"]:
            return {
                "status": "SUCCESS",
                "request": req,
                "inventory": stock,
                "note": "Request already allocated (idempotent)."
            }
        raise ValueError(
            f"Request '{request_id}' has already been allocated ({req['allocated_quantity']} units). Re-allocation or duplicate allocation is not permitted."
        )

    # Available stock plus already allocated to this specific request
    max_allocatable = stock["available"] + req["allocated_quantity"]
    if allocated_qty > max_allocatable:
        raise ValueError(
            f"Cannot allocate {allocated_qty} units. Only {stock['available']} available in stock."
        )

    # Adjust stock
    diff = allocated_qty - req["allocated_quantity"]
    stock["allocated"] += diff
    stock["available"] -= diff

    req["allocated_quantity"] = allocated_qty
    if allocated_qty >= req["requested_quantity"]:
        req["status"] = "ALLOCATED"
    elif allocated_qty > 0:
        req["status"] = "PARTIALLY_ALLOCATED"
    else:
        req["status"] = "PENDING"

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    req["updated_at"] = now_iso

    _audit_log.append({
        "timestamp": now_iso,
        "action": "ALLOCATE_INVENTORY",
        "request_id": request_id,
        "details": f"Allocated {allocated_qty} of {res_type} to {req['shelter_name']}. New status: {req['status']}.",
        "actor": "Resource Coordinator"
    })
    _save_to_disk()

    return {
        "status": "SUCCESS",
        "request": req,
        "inventory": stock,
    }


def fulfill_shelter_request(request_id: str, fulfilled_qty: int) -> Dict[str, Any]:
    """
    Marks allocated supplies as delivered/fulfilled.
    Enforces that fulfillment cannot exceed allocated quantities.
    """
    if fulfilled_qty <= 0:
        raise ValueError("Fulfilled quantity must be greater than zero.")

    req = next((r for r in _shelter_requests if r["id"] == request_id), None)
    if not req:
        raise ValueError(f"Request '{request_id}' not found.")

    if req["status"] == "FULFILLED":
        raise ValueError(f"Request '{request_id}' is already fulfilled.")

    already_fulfilled = req.get("fulfilled_quantity", 0)
    if already_fulfilled >= req["allocated_quantity"] and req["allocated_quantity"] > 0:
        raise ValueError(f"All allocated supplies ({req['allocated_quantity']} units) for request '{request_id}' have already been delivered.")

    if fulfilled_qty <= already_fulfilled:
        raise ValueError(f"Fulfilled quantity ({fulfilled_qty}) must exceed previously delivered units ({already_fulfilled}).")

    if fulfilled_qty > req["allocated_quantity"]:
        raise ValueError(
            f"Cannot fulfill {fulfilled_qty} units. Only {req['allocated_quantity']} units have been allocated."
        )

    req["fulfilled_quantity"] = fulfilled_qty
    if fulfilled_qty >= req["requested_quantity"]:
        req["status"] = "FULFILLED"
    elif fulfilled_qty > 0:
        req["status"] = "PARTIALLY_FULFILLED"

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    req["updated_at"] = now_iso

    _audit_log.append({
        "timestamp": now_iso,
        "action": "DELIVERY_FULFILLMENT",
        "request_id": request_id,
        "details": f"Delivered {fulfilled_qty} units to {req['shelter_name']}. Request status: {req['status']}.",
        "actor": "Logistics Dispatcher"
    })
    _save_to_disk()

    return {
        "status": "SUCCESS",
        "request": req,
    }


def get_audit_trail() -> List[Dict[str, Any]]:
    """Returns chronological audit trail of allocation actions."""
    return sorted(_audit_log, key=lambda x: x["timestamp"], reverse=True)


def calculate_demand_summary() -> Dict[str, Any]:
    """
    Computes aggregated resource demand, fulfillment ratios, and shortage metrics.
    """
    summary_by_type: Dict[str, Dict[str, Any]] = {}
    for item_name, item in _inventory_stock.items():
        summary_by_type[item_name] = {
            "resource_type": item_name,
            "unit": item["unit"],
            "requested": 0,
            "allocated": 0,
            "fulfilled": 0,
            "available_stock": item["available"],
            "shortage": 0,
        }

    for req in _shelter_requests:
        res = req["resource_type"]
        if res not in summary_by_type:
            summary_by_type[res] = {
                "resource_type": res,
                "unit": "Units",
                "requested": 0,
                "allocated": 0,
                "fulfilled": 0,
                "available_stock": 0,
                "shortage": 0,
            }
        summary_by_type[res]["requested"] += req["requested_quantity"]
        summary_by_type[res]["allocated"] += req["allocated_quantity"]
        summary_by_type[res]["fulfilled"] += req["fulfilled_quantity"]

    for item in summary_by_type.values():
        unmet = item["requested"] - item["allocated"]
        item["shortage"] = max(0, unmet - item["available_stock"])

    total_requests = len(_shelter_requests)
    fulfilled_requests = sum(1 for r in _shelter_requests if r["status"] == "FULFILLED")
    pending_requests = sum(1 for r in _shelter_requests if r["status"] in ("PENDING", "PARTIALLY_ALLOCATED"))

    return {
        "total_requests": total_requests,
        "fulfilled_requests": fulfilled_requests,
        "pending_requests": pending_requests,
        "demand_by_resource": list(summary_by_type.values()),
    }
