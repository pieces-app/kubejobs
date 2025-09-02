"""Utilities to label Kubernetes nodes with accelerator labels.

This enables shorthand selection in kubejobs via the `accelerator` parameter
(e.g., "h100x1", "a100-80x2") by ensuring nodes carry labels like:
- accel.family=h100
- accel.mem_gb=80 (optional)

Usage examples:
  python -m kubejobs.label_nodes --node_selector 'cloud.google.com/gke-nodepool=gpu-pool' --family h100 --mem_gb 80
  python -m kubejobs.label_nodes --node_selector 'cloud.google.com/gke-nodepool=gpu-pool' --family a100 --mem_gb 40

Requires kubeconfig context pointing to the target cluster.
"""

from __future__ import annotations

from typing import Optional, Dict
import logging

from kubernetes import client, config
from rich.logging import RichHandler
import fire

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RichHandler(markup=True)
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)


def label_nodes_for_accelerator(
    node_selector: str,
    family: str,
    mem_gb: Optional[int] = None,
    count: Optional[int] = None,
    overwrite: bool = True,
) -> Dict[str, int]:
    """Label nodes matching a selector with accelerator labels.

    Args:
        node_selector: Label selector for nodes to label, e.g.,
            'cloud.google.com/gke-nodepool=gpu-pool'.
        family: Accelerator family shorthand (e.g., 'h100', 'a100', 'l4').
        mem_gb: Optional memory in GB (e.g., 80 for H100 80GB, 40 for A100-40).
        count: Optional number of accelerators on the node (e.g., 1, 2, 8).
        overwrite: Whether to overwrite existing label values.

    Returns:
        A dict with counts of labeled nodes and total matched nodes.
    """
    family = family.lower().strip()
    if family not in {"h100", "a100", "l4"}:
        raise ValueError("family must be one of: h100, a100, l4")

    config.load_kube_config()
    v1 = client.CoreV1Api()
    nodes = v1.list_node(label_selector=node_selector).items
    logger.info(
        f"Found [bold]{len(nodes)}[/] node(s) for selector: [cyan]{node_selector}[/]"
    )

    patch_count = 0
    for node in nodes:
        name = node.metadata.name
        labels = node.metadata.labels or {}
        new_labels = labels.copy()
        new_labels["accel.family"] = family
        if mem_gb is not None:
            new_labels["accel.mem_gb"] = str(mem_gb)
        if count is not None:
            new_labels["accel.count"] = str(count)

        if not overwrite and (
            ("accel.family" in labels)
            or (mem_gb is not None and "accel.mem_gb" in labels)
            or (count is not None and "accel.count" in labels)
        ):
            logger.info(
                f"[yellow]Skipping[/] {name} (labels exist, overwrite=False)"
            )
            continue

        patch_body = {"metadata": {"labels": new_labels}}
        v1.patch_node(name, patch_body)
        patch_count += 1
        logger.info(
            f"Labeled node [green]{name}[/] with accel.family={family}"
            + (f", accel.mem_gb={mem_gb}" if mem_gb is not None else "")
            + (f", accel.count={count}" if count is not None else "")
        )

    logger.info(f"Updated [bold]{patch_count}[/] node(s)")
    return {"matched": len(nodes), "labeled": patch_count}


if __name__ == "__main__":
    fire.Fire(label_nodes_for_accelerator)
