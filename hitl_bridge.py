"""
hitl_bridge.py — Shared HITL queue holder.

A standalone module (not streamlit_app.py) so the cached graph closure
can import it without triggering a re-import of streamlit_app.py.

Usage:
    # In thread (before graph.invoke):
    import hitl_bridge
    hitl_bridge.queue = log_q

    # In streamlit_hitl_node (inside cached graph):
    import hitl_bridge
    q = hitl_bridge.queue
"""

queue = None  # set by run_pipeline_thread before graph.invoke()