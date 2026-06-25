import asyncio
from typing import List, Dict, Optional, Callable, Awaitable
from lib import gemini
from lib.telegram_client import search_groups, get_group_messages


async def auto_scan(
    client,  # TelegramClient instance (already connected)
    brand_name: str,
    duration_seconds: int = 300,  # 5 minutes
    progress_callback: Optional[Callable[[Dict], Awaitable[None]]] = None,
    save_callback: Optional[Callable[[List[Dict]], Awaitable[None]]] = None,  # 👈 new
) -> List[Dict]:
    """
    Automatically discovers groups, scrapes messages, and finds job seekers.
    Sends progress updates via callback, and optionally saves candidates via save_callback.
    """
    # 1. Generate keywords
    if progress_callback:
        await progress_callback({"step": "start", "message": "Generating search keywords..."})
    
    keywords = await gemini.generate_keywords(brand_name)
    if progress_callback:
        await progress_callback({"step": "keywords", "message": f"Generated {len(keywords)} keywords"})

    # 2. Search groups and scrape messages
    all_messages = []
    groups_searched = 0
    max_groups = min(len(keywords) * 5, 50)

    start_time = asyncio.get_event_loop().time()
    for i, kw in enumerate(keywords):
        if groups_searched >= max_groups:
            break
        if asyncio.get_event_loop().time() - start_time > duration_seconds:
            break

        if progress_callback:
            await progress_callback({
                "step": "searching",
                "message": f"Searching groups with keyword: {kw} ({i+1}/{len(keywords)})"
            })

        groups = await search_groups(client, kw, limit=5)
        for group in groups:
            groups_searched += 1
            if progress_callback:
                await progress_callback({
                    "step": "scraping",
                    "message": f"Scraping messages from {group.get('group_title', 'Unknown')}"
                })
            result = await get_group_messages(client, group['group_username'], limit=100)
            msgs = result.get('messages', [])
            for m in msgs:
                m['group_id'] = group.get('group_username')
                m['group_username'] = group.get('group_username', '')
                m['group_title'] = group.get('group_title', '')
                all_messages.append(m)

            if len(all_messages) > 5000:
                break
        if len(all_messages) > 5000:
            break

    if progress_callback:
        await progress_callback({
            "step": "analyzing",
            "message": f"Analyzing {len(all_messages)} messages for job seekers..."
        })

    # 3. Analyze messages
    candidates = await gemini.analyze_seekers(all_messages, brand_name)

    # 4. Save candidates if callback provided
    if save_callback and candidates:
        await save_callback(candidates)

    if progress_callback:
        await progress_callback({
            "step": "complete",
            "message": f"Found {len(candidates)} candidates",
            "candidates": candidates
        })

    return candidates
