"""
Multi-Agent Scheduling System using LangGraph.

Agents:
1. CalendarAgent - Queries all SA calendars for availability
2. DistributionAgent - Analyzes workload and recommends fair assignment
3. SchedulingAgent - Makes final scheduling decision and creates the meeting

The agents work together to automatically find the best time slot and interviewer.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TypedDict, Annotated
import operator
import pytz
import random

# LangGraph and LangChain imports (with fallback for demo mode)
try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("LangGraph not available - running in rule-based mode")

from services.interview_tracker import get_interview_tracker


class SchedulingState(TypedDict):
    """State passed between agents in the scheduling workflow."""
    # Input
    candidate_name: str
    candidate_email: str
    interview_type: str
    duration_minutes: int
    preferred_date_start: str
    preferred_date_end: str
    candidate_timezone: str  # Candidate's timezone - system finds SAs with overlap
    
    # Calendar Agent outputs
    all_sa_ids: List[str]
    available_slots: List[Dict]  # Slots with availability per SA
    compatible_sa_ids: List[str]  # SAs who have timezone overlap with candidate
    
    # Distribution Agent outputs
    ranked_slots: List[Dict]  # Slots ranked by fairness
    recommended_slot: Optional[Dict]
    recommended_sa: Optional[str]
    reasoning: str
    
    # Scheduling Agent outputs
    final_assignment: Optional[Dict]
    status: str
    error: Optional[str]


class SchedulingAgentSystem:
    """
    Multi-agent system for intelligent interview scheduling.
    
    Can run in two modes:
    1. LLM Mode: Uses OpenAI/other LLM for intelligent decisions
    2. Rule-based Mode: Uses deterministic rules (when LLM not available)
    """
    
    def __init__(self, use_llm: bool = False):
        self.tracker = get_interview_tracker()
        self.use_llm = use_llm and LANGGRAPH_AVAILABLE and os.environ.get('OPENAI_API_KEY')
        
        if self.use_llm:
            self._init_llm_workflow()
        else:
            print("Running in rule-based mode (no LLM)")
    
    def _init_llm_workflow(self):
        """Initialize LangGraph workflow with LLM agents."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1  # Low temperature for consistent decisions
        )
        
        # Build the graph
        workflow = StateGraph(SchedulingState)
        
        # Add nodes
        workflow.add_node("calendar_agent", self._calendar_agent_node)
        workflow.add_node("distribution_agent", self._distribution_agent_node)
        workflow.add_node("scheduling_agent", self._scheduling_agent_node)
        
        # Define edges
        workflow.set_entry_point("calendar_agent")
        workflow.add_edge("calendar_agent", "distribution_agent")
        workflow.add_edge("distribution_agent", "scheduling_agent")
        workflow.add_edge("scheduling_agent", END)
        
        self.workflow = workflow.compile()
    
    # ==================== Agent Nodes ====================
    
    def _calendar_agent_node(self, state: SchedulingState) -> Dict:
        """
        Calendar Agent: Fetches availability from all SA calendars.
        Automatically finds SAs who have overlapping working hours with the candidate.
        """
        print("📅 Calendar Agent: Checking all SA calendars...")
        
        # Get all active SAs
        all_sas = self.tracker.get_all_sas()
        all_sa_ids = [sa['id'] for sa in all_sas]
        
        # Get candidate timezone
        candidate_timezone = state.get('candidate_timezone', 'America/Los_Angeles')
        candidate_tz = pytz.timezone(candidate_timezone)
        
        # Find SAs with compatible timezones (have overlap with candidate)
        compatible_sas = []
        for sa in all_sas:
            sa_timezone = sa.get('timezone', 'America/Los_Angeles')
            sa_tz = pytz.timezone(sa_timezone)
            
            overlap_start, overlap_end = self._calculate_working_hour_overlap(
                interviewer_tz=sa_tz,
                candidate_tz=candidate_tz
            )
            
            if overlap_start < overlap_end:  # Has overlap
                compatible_sas.append({
                    **sa,
                    'overlap_start': overlap_start,
                    'overlap_end': overlap_end,
                    'overlap_hours': overlap_end - overlap_start
                })
                print(f"  ✅ {sa['name']} ({sa_timezone}): overlap {overlap_start}:00-{overlap_end}:00")
            else:
                print(f"  ❌ {sa['name']} ({sa_timezone}): no overlap with {candidate_timezone}")
        
        if not compatible_sas:
            print(f"⚠️ No SAs have overlapping work hours with candidate timezone {candidate_timezone}")
            return {
                "all_sa_ids": all_sa_ids,
                "compatible_sa_ids": [],
                "available_slots": []
            }
        
        compatible_sa_ids = [sa['id'] for sa in compatible_sas]
        
        # Get available slots for compatible SAs only
        available_slots = self._get_calendar_availability_per_sa(
            compatible_sas=compatible_sas,
            start_date=state['preferred_date_start'],
            end_date=state['preferred_date_end'],
            duration_minutes=state['duration_minutes'],
            candidate_timezone=candidate_timezone
        )
        
        return {
            "all_sa_ids": all_sa_ids,
            "compatible_sa_ids": compatible_sa_ids,
            "available_slots": available_slots
        }
    
    def _distribution_agent_node(self, state: SchedulingState) -> Dict:
        """
        Distribution Agent: Ranks slots and SAs by fairness.
        Enforces capacity limits - SAs at max weekly interviews are excluded.
        """
        print("⚖️ Distribution Agent: Analyzing workload distribution...")
        
        available_slots = state['available_slots']
        interview_type = state['interview_type']
        
        if not available_slots:
            return {
                "ranked_slots": [],
                "recommended_slot": None,
                "recommended_sa": None,
                "reasoning": "No available slots found in the date range."
            }
        
        # Get workload stats
        workload_stats = self.tracker.get_workload_stats(since_days=21)
        
        # Check for capacity warnings
        all_sas = self.tracker.get_all_sas()
        if len(all_sas) == 1:
            print("  ⚠️ Warning: Only 1 SA configured - no load balancing possible")
        
        sas_at_capacity = [
            s['sa_name'] for s in workload_stats.values() 
            if s.get('at_capacity', False)
        ]
        if sas_at_capacity:
            print(f"  ⚠️ SAs at weekly capacity: {', '.join(sas_at_capacity)}")
        
        # Rank each slot
        ranked_slots = []
        all_at_capacity = False
        
        for slot in available_slots:
            # Get SAs available for this slot
            available_sa_ids = [
                sa_id for sa_id, available in slot['availability'].items()
                if available
            ]
            
            if not available_sa_ids:
                continue
            
            # Rank SAs for this slot (excludes those at capacity)
            ranked_sas = self.tracker.rank_sas_for_assignment(
                available_sa_ids, 
                interview_type
            )
            
            if not ranked_sas:
                continue
            
            # Check if all SAs are at capacity
            if ranked_sas[0].get('_all_at_capacity'):
                all_at_capacity = True
                continue
            
            best_sa = ranked_sas[0]
            
            # Calculate slot score (based on best available SA)
            slot_score = best_sa['final_score']
            
            ranked_slots.append({
                **slot,
                'best_sa_id': best_sa['sa_id'],
                'best_sa_name': best_sa['sa_name'],
                'best_sa_score': slot_score,
                'best_sa_interview_count': best_sa['interview_count'],
                'specialty_match': best_sa.get('specialty_match', False),
                'all_ranked_sas': ranked_sas
            })
        
        # Sort by best SA score (highest first)
        ranked_slots.sort(key=lambda x: x['best_sa_score'], reverse=True)
        
        # Get recommendation
        if ranked_slots:
            recommended = ranked_slots[0]
            reasoning = self._generate_reasoning(recommended, workload_stats)
        else:
            recommended = None
            if all_at_capacity:
                # Build helpful message about capacity
                capacity_details = [
                    f"{s['sa_name']}: {s['weekly_count']}/{s['max_per_week']} this week"
                    for s in workload_stats.values()
                ]
                reasoning = f"All SAs are at weekly capacity. {'; '.join(capacity_details)}. Try next week or add more SAs."
            elif len(all_sas) == 0:
                reasoning = "No SAs configured. Please add Solution Architects to sa_config.json."
            elif len(all_sas) == 1:
                reasoning = "Only 1 SA configured and they have no available slots. Add more SAs for better coverage."
            else:
                reasoning = "No suitable slot/SA combination found in the date range."
        
        return {
            "ranked_slots": ranked_slots,
            "recommended_slot": recommended,
            "recommended_sa": recommended['best_sa_id'] if recommended else None,
            "reasoning": reasoning,
            "all_at_capacity": all_at_capacity
        }
    
    def _scheduling_agent_node(self, state: SchedulingState) -> Dict:
        """
        Scheduling Agent: Finalizes the assignment and creates the booking.
        Also creates the actual calendar event with Google Meet link.
        """
        print("✅ Scheduling Agent: Finalizing assignment...")
        
        recommended_slot = state.get('recommended_slot')
        recommended_sa = state.get('recommended_sa')
        
        if not recommended_slot or not recommended_sa:
            return {
                "final_assignment": None,
                "status": "failed",
                "error": "No suitable slot or SA available"
            }
        
        sa_info = self.tracker.get_sa(recommended_sa)
        
        # Create the interview record
        interview = self.tracker.add_interview(
            candidate_name=state['candidate_name'],
            candidate_email=state['candidate_email'],
            interview_type=state['interview_type'],
            scheduled_time=recommended_slot['start'],
            duration_minutes=state['duration_minutes'],
            assigned_sa_id=recommended_sa,
            notes=f"Auto-scheduled. {state.get('reasoning', '')}"
        )
        
        # Send calendar invites via email with RSVP
        calendar_event = None
        meet_link = None
        try:
            from services.calendar_service import get_calendar_service
            cal_service = get_calendar_service()
            
            if cal_service.is_authenticated():
                print("📧 Invite Agent: Sending calendar invites with RSVP...")
                
                # Get interview type display name
                interview_types = {
                    'tech_screen': 'Technical Screen',
                    'system_design': 'System Design',
                    'coding': 'Coding Interview',
                    'ml_ai': 'ML/AI Deep Dive',
                    'data': 'Data Engineering',
                    'architecture': 'Architecture Review',
                }
                type_display = interview_types.get(state['interview_type'], state['interview_type'])
                
                # Create event title and description
                title = f"Interview: {state['candidate_name']} - {type_display}"
                description = f"""Technical Interview

Candidate: {state['candidate_name']}
Email: {state['candidate_email']}
Type: {type_display}
Duration: {state['duration_minutes']} minutes

Interviewer: {sa_info['name'] if sa_info else 'TBD'}

Please accept this invite to confirm your attendance.

---
Scheduled by TA Interview Scheduler
{state.get('reasoning', '')}
"""
                
                # Build attendee list
                attendees = [state['candidate_email']]
                if sa_info and sa_info.get('email'):
                    attendees.append(sa_info['email'])
                
                # Send invites - creates event on organizer's calendar
                # and sends email invites to all attendees
                calendar_event = cal_service.send_interview_invite(
                    title=title,
                    start_time=recommended_slot['start'],
                    end_time=recommended_slot['end'],
                    description=description,
                    attendees=attendees
                )
                
                if calendar_event:
                    meet_link = calendar_event.get('meet_link', '')
        except Exception as e:
            print(f"⚠️ Calendar invite failed (interview still recorded locally): {e}")
        
        final_assignment = {
            "interview_id": interview['id'],
            "candidate_name": state['candidate_name'],
            "candidate_email": state['candidate_email'],
            "interview_type": state['interview_type'],
            "scheduled_time": recommended_slot['start'],
            "scheduled_end": recommended_slot['end'],
            "date_display": recommended_slot['date'],
            "time_display": recommended_slot['time'],
            "duration_minutes": state['duration_minutes'],
            "assigned_sa_id": recommended_sa,
            "assigned_sa_name": sa_info['name'] if sa_info else 'Unknown',
            "assigned_sa_email": sa_info['email'] if sa_info else '',
            "reasoning": state.get('reasoning', ''),
            "calendar_event": calendar_event,
            "meet_link": meet_link,
        }
        
        return {
            "final_assignment": final_assignment,
            "status": "success",
            "error": None
        }
    
    # ==================== Helper Methods ====================
    
    def _get_calendar_availability(
        self,
        sa_ids: List[str],
        start_date: str,
        end_date: str,
        duration_minutes: int,
        interviewer_timezone: str = 'America/Los_Angeles',
        candidate_timezone: str = 'America/Los_Angeles'
    ) -> List[Dict]:
        """
        Get calendar availability for all SAs.
        Finds slots that are within working hours for BOTH the interviewer AND candidate.
        
        Args:
            sa_ids: List of SA IDs to check
            start_date: Start date for search
            end_date: End date for search
            duration_minutes: Interview duration
            interviewer_timezone: Interviewer's timezone
            candidate_timezone: Candidate's timezone for overlap calculation
        """
        from dateutil import parser as date_parser
        
        # Parse dates
        if isinstance(start_date, str):
            start = date_parser.parse(start_date).date()
        else:
            start = start_date
        
        if isinstance(end_date, str):
            end = date_parser.parse(end_date).date()
        else:
            end = end_date
        
        # Use the provided interviewer timezone
        sa_timezone = interviewer_timezone
        
        sa_tz = pytz.timezone(sa_timezone)
        candidate_tz = pytz.timezone(candidate_timezone)
        
        # Calculate overlapping working hours (9 AM - 5 PM for both parties)
        overlap_start, overlap_end = self._calculate_working_hour_overlap(
            interviewer_tz=sa_tz,
            candidate_tz=candidate_tz,
            work_start=9,
            work_end=17
        )
        
        print(f"🕐 Timezone overlap: {overlap_start}:00 - {overlap_end}:00 (in interviewer's {sa_timezone})")
        print(f"   Candidate TZ: {candidate_timezone}")
        
        if overlap_start >= overlap_end:
            print("⚠️ No overlapping working hours between timezones!")
            return []
        
        slots = []
        current = start
        
        # Try to use real calendar service
        try:
            from services.calendar_service import get_calendar_service
            cal_service = get_calendar_service()
            
            if cal_service.is_authenticated():
                # Use real calendar data
                # Map SA IDs to calendar IDs
                sa_calendar_map = {}
                for sa in self.tracker.get_all_sas():
                    sa_calendar_map[sa['id']] = sa.get('calendar_id', sa['email'])
                
                calendar_ids = list(sa_calendar_map.values())
                
                start_dt = sa_tz.localize(datetime.combine(start, datetime.min.time().replace(hour=overlap_start)))
                end_dt = sa_tz.localize(datetime.combine(end, datetime.min.time().replace(hour=overlap_end)))
                
                print(f"📅 Using real calendar data for: {calendar_ids}")
                real_slots = cal_service.find_available_slots(
                    calendar_emails=calendar_ids,
                    start_date=start_dt,
                    end_date=end_dt,
                    slot_duration_minutes=duration_minutes,
                    work_start_hour=overlap_start,
                    work_end_hour=overlap_end,
                    timezone=sa_timezone
                )
                
                # Map calendar IDs back to SA IDs and add candidate time display
                for slot in real_slots:
                    sa_availability = {}
                    for sa_id, cal_id in sa_calendar_map.items():
                        sa_availability[sa_id] = slot['availability'].get(cal_id, False)
                    slot['availability'] = sa_availability
                    
                    # Add candidate's local time for display
                    slot_start = date_parser.parse(slot['start'])
                    candidate_local = slot_start.astimezone(candidate_tz)
                    slot['candidate_time'] = candidate_local.strftime('%I:%M %p')
                    slot['candidate_timezone'] = candidate_timezone
                
                return real_slots
        except Exception as e:
            print(f"Calendar service error, using simulated data: {e}")
        
        # Fall back to simulated availability
        # Get all scheduled interviews to check for conflicts
        scheduled_interviews = self.tracker.get_upcoming_interviews()
        
        # Build a map of SA -> list of busy time ranges
        sa_busy_times = {sa_id: [] for sa_id in sa_ids}
        for interview in scheduled_interviews:
            sa_id = interview.get('assigned_sa_id')
            if sa_id in sa_busy_times:
                try:
                    from dateutil import parser as dt_parser
                    interview_start = dt_parser.parse(interview['scheduled_time'])
                    interview_duration = interview.get('duration_minutes', 60)
                    interview_end = interview_start + timedelta(minutes=interview_duration)
                    sa_busy_times[sa_id].append((interview_start, interview_end))
                except Exception as e:
                    print(f"Error parsing interview time: {e}")
        
        # Use seeded random for consistency but different per day
        while current <= end:
            if current.weekday() < 5:  # Skip weekends
                for hour in range(overlap_start, overlap_end):
                    if hour + (duration_minutes / 60) <= overlap_end:
                        slot_start = sa_tz.localize(
                            datetime.combine(current, datetime.min.time().replace(hour=hour))
                        )
                        slot_end = slot_start + timedelta(minutes=duration_minutes)
                        
                        # Check availability for each SA
                        availability = {}
                        workload = self.tracker.get_interview_counts(since_days=21)
                        
                        for sa_id in sa_ids:
                            # First check if SA has a scheduled interview at this time
                            is_booked = False
                            for busy_start, busy_end in sa_busy_times.get(sa_id, []):
                                # Check for overlap
                                if not (slot_end <= busy_start or slot_start >= busy_end):
                                    is_booked = True
                                    break
                            
                            if is_booked:
                                availability[sa_id] = False
                            else:
                                # Base availability ~80% (simulate other meetings)
                                # Reduce slightly if overloaded
                                count = workload.get(sa_id, 0)
                                base_prob = 0.8 - (count * 0.02)
                                base_prob = max(0.5, min(0.95, base_prob))
                                
                                # Add some randomness based on day/hour
                                seed = hash(f"{current}_{hour}_{sa_id}") % 1000
                                random.seed(seed)
                                availability[sa_id] = random.random() < base_prob
                        
                        # Only include if at least one SA available
                        if any(availability.values()):
                            # Add candidate's local time for display
                            candidate_local = slot_start.astimezone(candidate_tz)
                            
                            slots.append({
                                'start': slot_start.isoformat(),
                                'end': slot_end.isoformat(),
                                'date': current.strftime('%Y-%m-%d'),
                                'time': slot_start.strftime('%I:%M %p'),
                                'candidate_time': candidate_local.strftime('%I:%M %p'),
                                'candidate_timezone': candidate_timezone,
                                'availability': availability
                            })
            
            current += timedelta(days=1)
        
        # Reset random seed
        random.seed()
        return slots
    
    def _get_calendar_availability_per_sa(
        self,
        compatible_sas: List[Dict],
        start_date: str,
        end_date: str,
        duration_minutes: int,
        candidate_timezone: str
    ) -> List[Dict]:
        """
        Get calendar availability checking each SA's timezone individually.
        Only returns slots within each SA's overlap window with the candidate.
        """
        from dateutil import parser as date_parser
        
        # Parse dates
        if isinstance(start_date, str):
            start = date_parser.parse(start_date).date()
        else:
            start = start_date
        
        if isinstance(end_date, str):
            end = date_parser.parse(end_date).date()
        else:
            end = end_date
        
        candidate_tz = pytz.timezone(candidate_timezone)
        
        # Get scheduled interviews for conflict checking
        scheduled_interviews = self.tracker.get_upcoming_interviews()
        sa_busy_times = {}
        for interview in scheduled_interviews:
            sa_id = interview.get('assigned_sa_id')
            if sa_id not in sa_busy_times:
                sa_busy_times[sa_id] = []
            try:
                interview_start = date_parser.parse(interview['scheduled_time'])
                interview_duration = interview.get('duration_minutes', 60)
                interview_end = interview_start + timedelta(minutes=interview_duration)
                sa_busy_times[sa_id].append((interview_start, interview_end))
            except Exception as e:
                print(f"Error parsing interview time: {e}")
        
        # Try real calendar service first
        try:
            from services.calendar_service import get_calendar_service
            cal_service = get_calendar_service()
            
            if cal_service.is_authenticated():
                return self._get_real_calendar_slots_per_sa(
                    compatible_sas, start, end, duration_minutes, 
                    candidate_tz, cal_service, sa_busy_times
                )
        except Exception as e:
            print(f"Calendar service error, using simulated data: {e}")
        
        # Fall back to simulated availability
        all_slots = {}  # slot_key -> {slot_data, availability: {sa_id: bool}}
        
        for sa in compatible_sas:
            sa_id = sa['id']
            sa_tz = pytz.timezone(sa.get('timezone', 'America/Los_Angeles'))
            overlap_start = sa['overlap_start']
            overlap_end = sa['overlap_end']
            
            current = start
            while current <= end:
                if current.weekday() < 5:  # Skip weekends
                    for hour in range(overlap_start, overlap_end):
                        if hour + (duration_minutes / 60) <= overlap_end:
                            slot_start = sa_tz.localize(
                                datetime.combine(current, datetime.min.time().replace(hour=hour))
                            )
                            slot_end = slot_start + timedelta(minutes=duration_minutes)
                            
                            # Check if SA is booked at this time
                            is_booked = False
                            for busy_start, busy_end in sa_busy_times.get(sa_id, []):
                                if not (slot_end <= busy_start or slot_start >= busy_end):
                                    is_booked = True
                                    break
                            
                            # Create slot key (use UTC for consistency)
                            slot_utc = slot_start.astimezone(pytz.UTC)
                            slot_key = slot_utc.isoformat()
                            
                            if slot_key not in all_slots:
                                candidate_local = slot_start.astimezone(candidate_tz)
                                all_slots[slot_key] = {
                                    'start': slot_start.isoformat(),
                                    'end': slot_end.isoformat(),
                                    'start_utc': slot_key,
                                    'date': current.strftime('%Y-%m-%d'),
                                    'time': slot_start.strftime('%I:%M %p'),
                                    'candidate_time': candidate_local.strftime('%I:%M %p'),
                                    'candidate_timezone': candidate_timezone,
                                    'availability': {}
                                }
                            
                            # Simulate availability (80% base, reduced if overloaded)
                            if is_booked:
                                all_slots[slot_key]['availability'][sa_id] = False
                            else:
                                workload = self.tracker.get_interview_counts(since_days=21)
                                count = workload.get(sa_id, 0)
                                base_prob = 0.8 - (count * 0.02)
                                base_prob = max(0.5, min(0.95, base_prob))
                                
                                seed = hash(f"{current}_{hour}_{sa_id}") % 1000
                                random.seed(seed)
                                all_slots[slot_key]['availability'][sa_id] = random.random() < base_prob
                
                current += timedelta(days=1)
        
        random.seed()
        
        # Filter to only slots where at least one SA is available
        slots = [s for s in all_slots.values() if any(s['availability'].values())]
        slots.sort(key=lambda x: x['start_utc'])
        
        return slots
    
    def _get_real_calendar_slots_per_sa(
        self,
        compatible_sas: List[Dict],
        start: datetime,
        end: datetime,
        duration_minutes: int,
        candidate_tz: pytz.timezone,
        cal_service,
        sa_busy_times: Dict[str, List] = None
    ) -> List[Dict]:
        """
        Get real calendar slots for each SA based on their timezone overlap.
        Also checks for conflicts with locally scheduled interviews.
        """
        from dateutil import parser as date_parser
        
        if sa_busy_times is None:
            sa_busy_times = {}
        
        all_slots = {}
        
        for sa in compatible_sas:
            sa_id = sa['id']
            sa_tz = pytz.timezone(sa.get('timezone', 'America/Los_Angeles'))
            overlap_start = sa['overlap_start']
            overlap_end = sa['overlap_end']
            calendar_id = sa.get('calendar_id', sa['email'])
            
            # Query this SA's calendar for their overlap window
            start_dt = sa_tz.localize(datetime.combine(start, datetime.min.time().replace(hour=overlap_start)))
            end_dt = sa_tz.localize(datetime.combine(end, datetime.min.time().replace(hour=overlap_end)))
            
            print(f"📅 Checking {sa['name']}'s calendar ({overlap_start}:00-{overlap_end}:00 {sa.get('timezone')})")
            
            try:
                real_slots = cal_service.find_available_slots(
                    calendar_emails=[calendar_id],
                    start_date=start_dt,
                    end_date=end_dt,
                    slot_duration_minutes=duration_minutes,
                    work_start_hour=overlap_start,
                    work_end_hour=overlap_end,
                    timezone=sa.get('timezone', 'America/Los_Angeles')
                )
                
                for slot in real_slots:
                    slot_start = date_parser.parse(slot['start'])
                    slot_end = date_parser.parse(slot['end'])
                    slot_utc = slot_start.astimezone(pytz.UTC)
                    slot_key = slot_utc.isoformat()
                    
                    if slot_key not in all_slots:
                        candidate_local = slot_start.astimezone(candidate_tz)
                        all_slots[slot_key] = {
                            'start': slot['start'],
                            'end': slot['end'],
                            'start_utc': slot_key,
                            'date': slot['date'],
                            'time': slot['time'],
                            'candidate_time': candidate_local.strftime('%I:%M %p'),
                            'candidate_timezone': str(candidate_tz),
                            'availability': {}
                        }
                    
                    # Check Google Calendar availability
                    is_available = slot['availability'].get(calendar_id, False)
                    
                    # Also check for conflicts with locally scheduled interviews
                    if is_available and sa_id in sa_busy_times:
                        for busy_start, busy_end in sa_busy_times[sa_id]:
                            # Check for overlap
                            if not (slot_end <= busy_start or slot_start >= busy_end):
                                is_available = False
                                print(f"  ⚠️ {sa['name']} has existing interview at {slot['time']}")
                                break
                    all_slots[slot_key]['availability'][sa_id] = is_available
                    
            except Exception as e:
                print(f"  Error checking {sa['name']}'s calendar: {e}")
        
        # Filter to only slots where at least one SA is available
        slots = [s for s in all_slots.values() if any(s['availability'].values())]
        slots.sort(key=lambda x: x['start_utc'])
        
        return slots
    
    def _calculate_working_hour_overlap(
        self,
        interviewer_tz: pytz.timezone,
        candidate_tz: pytz.timezone,
        work_start: int = 9,
        work_end: int = 17
    ) -> tuple:
        """
        Calculate the overlapping working hours between two timezones.
        
        Args:
            interviewer_tz: Interviewer's timezone
            candidate_tz: Candidate's timezone
            work_start: Start of work day (hour, e.g., 9 for 9 AM)
            work_end: End of work day (hour, e.g., 17 for 5 PM)
            
        Returns:
            Tuple of (overlap_start, overlap_end) in interviewer's timezone
        """
        # Use a reference date
        ref_date = datetime(2025, 1, 6)  # A Monday
        
        # Interviewer's working hours in their timezone
        interviewer_work_start = interviewer_tz.localize(
            datetime.combine(ref_date, datetime.min.time().replace(hour=work_start))
        )
        interviewer_work_end = interviewer_tz.localize(
            datetime.combine(ref_date, datetime.min.time().replace(hour=work_end))
        )
        
        # Candidate's working hours in their timezone, converted to interviewer's TZ
        candidate_work_start = candidate_tz.localize(
            datetime.combine(ref_date, datetime.min.time().replace(hour=work_start))
        ).astimezone(interviewer_tz)
        candidate_work_end = candidate_tz.localize(
            datetime.combine(ref_date, datetime.min.time().replace(hour=work_end))
        ).astimezone(interviewer_tz)
        
        # Find overlap
        overlap_start = max(interviewer_work_start.hour, candidate_work_start.hour)
        overlap_end = min(interviewer_work_end.hour, candidate_work_end.hour)
        
        return (overlap_start, overlap_end)
    
    def _generate_reasoning(self, slot: Dict, workload_stats: Dict) -> str:
        """Generate human-readable reasoning for the recommendation."""
        sa_id = slot['best_sa_id']
        sa_name = slot['best_sa_name']
        sa_stats = workload_stats.get(sa_id, {})
        
        interview_count = sa_stats.get('interview_count', 0)
        deviation = sa_stats.get('deviation', 0)
        specialty_match = slot.get('specialty_match', False)
        
        reasons = []
        
        if deviation < 0:
            reasons.append(f"{sa_name} has conducted {interview_count} interviews in the last 3 weeks, which is {abs(deviation):.1f} below the team average")
        elif deviation == 0:
            reasons.append(f"{sa_name} has conducted exactly the fair share of interviews")
        else:
            reasons.append(f"{sa_name} is slightly above average but is the best available option")
        
        if specialty_match:
            reasons.append("their specialty matches this interview type")
        
        reasons.append(f"available at {slot['time']} on {slot['date']}")
        
        return f"Recommended {sa_name} because: " + "; ".join(reasons) + "."
    
    # ==================== Public API ====================
    
    def schedule_interview(
        self,
        candidate_name: str,
        candidate_email: str,
        interview_type: str,
        duration_minutes: int = 60,
        preferred_date_start: Optional[str] = None,
        preferred_date_end: Optional[str] = None,
        candidate_timezone: str = 'America/Los_Angeles',
        **kwargs  # Accept but ignore interviewer_timezone for backwards compatibility
    ) -> Dict:
        """
        Automatically schedule an interview using the multi-agent system.
        
        The system automatically finds SAs who have overlapping working hours
        with the candidate's timezone.
        
        Args:
            candidate_name: Name of the candidate
            candidate_email: Email of the candidate
            interview_type: Type of interview
            duration_minutes: Duration of interview
            preferred_date_start: Start of date range (default: today)
            preferred_date_end: End of date range (default: 7 days from now)
            candidate_timezone: Candidate's timezone - system finds compatible SAs
            
        Returns:
            Dict with scheduling result including assigned SA and time
        """
        # Set default dates (use UTC for consistency)
        now = datetime.now(pytz.UTC)
        
        if not preferred_date_start:
            preferred_date_start = now.date().isoformat()
        if not preferred_date_end:
            preferred_date_end = (now + timedelta(days=7)).date().isoformat()
        
        # Initial state
        initial_state: SchedulingState = {
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "interview_type": interview_type,
            "duration_minutes": duration_minutes,
            "preferred_date_start": preferred_date_start,
            "preferred_date_end": preferred_date_end,
            "candidate_timezone": candidate_timezone,
            "all_sa_ids": [],
            "compatible_sa_ids": [],
            "available_slots": [],
            "ranked_slots": [],
            "recommended_slot": None,
            "recommended_sa": None,
            "reasoning": "",
            "final_assignment": None,
            "status": "pending",
            "error": None
        }
        
        if self.use_llm and hasattr(self, 'workflow'):
            # Run LangGraph workflow
            result = self.workflow.invoke(initial_state)
        else:
            # Run agents sequentially in rule-based mode
            result = initial_state
            result.update(self._calendar_agent_node(result))
            result.update(self._distribution_agent_node(result))
            result.update(self._scheduling_agent_node(result))
        
        return result
    
    def get_scheduling_preview(
        self,
        interview_type: str,
        duration_minutes: int = 60,
        preferred_date_start: Optional[str] = None,
        preferred_date_end: Optional[str] = None,
        candidate_timezone: str = 'America/Los_Angeles',
        top_n: int = 5,
        **kwargs  # Accept but ignore interviewer_timezone for backwards compatibility
    ) -> Dict:
        """
        Get a preview of scheduling options without actually booking.
        
        Returns top N recommendations with reasoning.
        """
        now = datetime.now(pytz.UTC)
        
        if not preferred_date_start:
            preferred_date_start = now.date().isoformat()
        if not preferred_date_end:
            preferred_date_end = (now + timedelta(days=7)).date().isoformat()
        
        # Get all SAs and find those with timezone overlap
        all_sas = self.tracker.get_all_sas()
        candidate_tz = pytz.timezone(candidate_timezone)
        
        compatible_sas = []
        for sa in all_sas:
            sa_timezone = sa.get('timezone', 'America/Los_Angeles')
            sa_tz = pytz.timezone(sa_timezone)
            
            overlap_start, overlap_end = self._calculate_working_hour_overlap(
                interviewer_tz=sa_tz,
                candidate_tz=candidate_tz
            )
            
            if overlap_start < overlap_end:
                compatible_sas.append({
                    **sa,
                    'overlap_start': overlap_start,
                    'overlap_end': overlap_end,
                    'overlap_hours': overlap_end - overlap_start
                })
        
        if not compatible_sas:
            return {
                "total_slots_found": 0,
                "recommendations": [],
                "workload_stats": {},
                "error": f"No SAs have overlapping work hours with candidate timezone {candidate_timezone}"
            }
        
        # Get availability for compatible SAs
        available_slots = self._get_calendar_availability_per_sa(
            compatible_sas=compatible_sas,
            start_date=preferred_date_start,
            end_date=preferred_date_end,
            duration_minutes=duration_minutes,
            candidate_timezone=candidate_timezone
        )
        
        # Rank slots
        workload_stats = self.tracker.get_workload_stats(since_days=21)
        
        ranked_slots = []
        for slot in available_slots:
            available_sa_ids = [
                sa_id for sa_id, available in slot['availability'].items()
                if available
            ]
            
            if not available_sa_ids:
                continue
            
            ranked_sas = self.tracker.rank_sas_for_assignment(
                available_sa_ids, 
                interview_type
            )
            
            if ranked_sas:
                best_sa = ranked_sas[0]
                ranked_slots.append({
                    **slot,
                    'best_sa_id': best_sa['sa_id'],
                    'best_sa_name': best_sa['sa_name'],
                    'best_sa_score': best_sa['final_score'],
                    'best_sa_interview_count': best_sa['interview_count'],
                    'specialty_match': best_sa.get('specialty_match', False),
                    'reasoning': self._generate_reasoning(
                        {**slot, 'best_sa_id': best_sa['sa_id'], 'best_sa_name': best_sa['sa_name'], 'specialty_match': best_sa.get('specialty_match', False)},
                        workload_stats
                    )
                })
        
        ranked_slots.sort(key=lambda x: x['best_sa_score'], reverse=True)
        
        return {
            "total_slots_found": len(available_slots),
            "recommendations": ranked_slots[:top_n],
            "workload_stats": workload_stats
        }


# Singleton getter
_agent_system = None

def get_scheduling_agent() -> SchedulingAgentSystem:
    """Get the singleton SchedulingAgentSystem instance."""
    global _agent_system
    if _agent_system is None:
        _agent_system = SchedulingAgentSystem(use_llm=False)  # Default to rule-based
    return _agent_system

